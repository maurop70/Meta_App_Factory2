import os
import logging
import sqlite3
import datetime
import time
import csv
import json
import io
import aiofiles
from typing import Optional, Dict, Any
import jwt
import uuid
from datetime import datetime, timedelta, timezone
import concurrent.futures
from itertools import islice
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, BackgroundTasks, Header, Body, Depends, Security, Response, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse


from dotenv import load_dotenv
import base64
from fastapi import Request

# Initialize Environment
_here = os.path.dirname(os.path.abspath(__file__))
_erp  = os.path.dirname(_here)
_factory = os.path.dirname(_erp)

# I/O Leak Patch: Only hit the disk for .env if variables aren't inherited via spawn
if not os.environ.get("JWT_PRIVATE_KEY_B64"):
    env_path = os.path.join(_factory, '.env')
    load_dotenv(env_path)

# Initialize Standard Output Logging
import sys
logger = logging.getLogger("MaintenanceBackend")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if logger.hasHandlers():
    logger.handlers.clear()

# Strictly delegate logs to stdout for Docker daemon rotation
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

if not os.environ.get("JWT_PRIVATE_KEY_B64"):
    logger.info(f"Loading .env from: {env_path}")


# --- CRYPTOGRAPHIC CONFIGURATION ---
priv_b64 = os.environ.get("JWT_PRIVATE_KEY_B64")
pub_b64 = os.environ.get("JWT_PUBLIC_KEY_B64")

if not priv_b64 or not pub_b64:
    raise RuntimeError("FATAL: JWT_PRIVATE_KEY_B64 or JWT_PUBLIC_KEY_B64 missing from environment.")

PRIVATE_KEY = base64.b64decode(priv_b64).decode('utf-8')
PUBLIC_KEY = base64.b64decode(pub_b64).decode('utf-8')

ALGORITHM = "RS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 15

# --- IN-MEMORY JTI BLACKLIST ---
REVOKED_JTIS = set()
security = HTTPBearer()

def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "role": role.upper(),
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "jti": jti
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "role": role.upper(),
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "jti": jti,
        "type": "refresh"
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)

def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        if payload.get("jti") in REVOKED_JTIS:
            raise HTTPException(status_code=401, detail="Token Revoked (JTI Blacklisted).")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token Expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Cryptographic Verification Failed.")
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from contextlib import asynccontextmanager

from local_db import get_db_connection
import os
from fpdf import FPDF


# Ingestion Logic for Orchestration Boundary
GLOBAL_AI_DIRECTIVE_CONTEXT = ""

@asynccontextmanager
async def lifespan(app: FastAPI):
    global GLOBAL_AI_DIRECTIVE_CONTEXT
    directive_path = os.path.join(_here, "GLOBAL_AI_DIRECTIVE.md")
    try:
        if os.path.exists(directive_path):
            with open(directive_path, "r", encoding="utf-8") as f:
                GLOBAL_AI_DIRECTIVE_CONTEXT = f.read()
            logger.info("Orchestration Boundary Engaged: GLOBAL_AI_DIRECTIVE.md fully loaded into active system memory.")
        else:
            logger.warning("Orchestration Boundary Warning: GLOBAL_AI_DIRECTIVE.md not found at /app/GLOBAL_AI_DIRECTIVE.md.")
    except Exception as e:
        logger.error(f"Failed to ingest GLOBAL_AI_DIRECTIVE.md: {e}")
    yield
    # Shutdown logic clears memory

app = FastAPI(title="Maintenance Work Order API - Global ERP Connected", lifespan=lifespan)

# Serve frontend — index.html lives alongside this backend file
_frontend_dir = _here  # Meta_App_Factory/ERP/Maintenance_Work_Order/

@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(os.path.join(_frontend_dir, "index.html"))

app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")

# CORS: Decoupled frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
        "http://localhost:5175", "http://127.0.0.1:5175",
        "http://localhost:5176", "http://127.0.0.1:5176"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GLOBAL ERP DATA MODELS ---

class WorkOrderSubmit(BaseModel):
    reported_by: str
    asset_id: str
    issue_description: str

class StatusUpdate(BaseModel):
    order_id: str
    new_status: str # PENDING, IN_PROGRESS, COMPLETE
    user_id: str 
    resolution_notes: str = ""

class UserSubmit(BaseModel):
    name: str
    role_id: str           # FK to erp_roles.id — carries full permissions
    authorization_level: str # TECH, MANAGER, ADMIN
    phone_number: str
    pin_code: str
    department_id: str

class EquipmentSubmit(BaseModel):
    machine_name: str
    location: str
    department_id: str
    operational_status: str = "OPERATIONAL"

class EquipmentIngestionRecord(BaseModel):
    equipment_id: str = Field(..., description="Unique Equipment Identifier")
    nomenclature: str = Field(..., min_length=2, description="Human-readable equipment name")
    category: str = Field(..., description="Equipment category/type")
    status: str = Field(default="ACTIVE", description="Strictly enforced operational state")
    department: str = Field(..., description="Localization matching Phase 34.5 taxonomy")
    assigned_tech_id: Optional[str] = None
    
    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v):
        allowed_states = {"ACTIVE", "DEGRADED", "OFFLINE"}
        if str(v).upper() not in allowed_states:
            raise ValueError(f"Structural Violation: Status must be one of {allowed_states}")
        return str(v).upper()

    @field_validator('assigned_tech_id', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

class EquipmentStatusUpdate(BaseModel):
    status: str = Field(..., description="ACTIVE, DEGRADED, OFFLINE")
    assigned_tech_id: Optional[str] = None

    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v):
        allowed_states = {"ACTIVE", "DEGRADED", "OFFLINE"}
        if str(v).upper() not in allowed_states:
            raise ValueError(f"Structural Violation: Status must be one of {allowed_states}")
        return str(v).upper()

class EmployeeIngestionRecord(BaseModel):
    id: str = Field(..., description="Unique Employee Identifier (e.g., U-001)")
    name: str = Field(..., min_length=2, max_length=100)
    authorization_level: str = Field(..., description="Mapped Role (e.g., ADMIN, TECH)")
    pin_code: str = Field(..., min_length=4, max_length=12, description="Raw PIN to be hashed")
    is_active: int = Field(default=1, ge=0, le=1)
    
    # [PHASE 34.5 UNIFICATION INJECTIONS]
    department: str = Field(..., min_length=2, description="Physical operational department")
    reports_to_hm_id: Optional[str] = None
    
    @field_validator('reports_to_hm_id', mode='after')
    @classmethod
    def require_hm_for_tech(cls, v, info):
        role = info.data.get('authorization_level', '').upper()
        if role in ["TECH", "TECHNICIAN"] and not v:
            raise ValueError("Structural Violation: A TECHNICIAN must be assigned a reporting HM.")
        return v

    @field_validator('authorization_level', mode='before')
    @classmethod
    def validate_role(cls, v):
        allowed_roles = {"ADMIN", "ADMINISTRATOR", "DM", "HM", "TECHNICIAN", "TECH"}
        if str(v).upper() not in allowed_roles:
            raise ValueError(f"Invalid authorization_level. Must be one of {allowed_roles}")
        return str(v).upper()

# [PHASE 34.9] Parts Catalog Ingestion Schema
class PartIngestionRecord(BaseModel):
    part_id: str = Field(..., description="Unique Part Identifier (e.g., PRT-001)")
    nomenclature: str = Field(..., min_length=2, description="Human-readable part name")
    category: str = Field(..., description="Part category (e.g., ELECTRICAL, HYDRAULIC, CONSUMABLE)")
    quantity_on_hand: int = Field(default=0, ge=0, description="Initial physical stock count")
    reorder_threshold: int = Field(default=5, ge=0, description="Minimum threshold before alert")
    unit_cost: float = Field(default=0.0, ge=0.0, description="Financial cost per unit")

    @field_validator('category', mode='before')
    @classmethod
    def enforce_uppercase_category(cls, v):
        return str(v).upper()

class PartConsumptionPayload(BaseModel):
    part_id: str = Field(..., description="Unique Part Identifier")
    quantity_consumed: int = Field(..., gt=0, description="Amount to deduct and allocate")

class PinVerify(BaseModel):
    employee_id: str = Field(..., description="Unique ERP Employee Identifier")
    pin: str = Field(..., min_length=4, max_length=12, description="First-party ERP Employee PIN")

class MWOIngestionRecord(BaseModel):
    mwo_id: str = Field(..., description="Unique Work Order Identifier")
    equipment_id: str = Field(..., description="Target machine or asset identifier")
    description: str = Field(..., min_length=5, description="Contextual issue description")
    
    status: str = Field(default="UNASSIGNED", description="Strictly enforced operational state")
    dm_urgency: str = Field(default="Normal")
    hm_priority: str = Field(default="Normal")
    
    assigned_tech: Optional[str] = None
    consumed_sku: Optional[str] = None
    manual_log: Optional[str] = None
    archival_pdf_path: Optional[str] = None
    # STRICT TYPING DEPLOYED. Pydantic handles ISO 8601 validation natively.
    start_date: Optional[datetime] = None 
    
    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v):
        allowed_states = {"UNASSIGNED", "ASSIGNED", "IN_PROGRESS", "PENDING_REVIEW", "COMPLETED"}
        if str(v).upper() not in allowed_states:
            raise ValueError(f"Structural Violation: Status must be one of {allowed_states}")
        return str(v).upper()

    @field_validator('dm_urgency', 'hm_priority', mode='before')
    @classmethod
    def validate_urgency(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()): 
            return "Normal"
        allowed = {"Low", "Normal", "High", "Critical"}
        # Case-insensitive match, strict formatting
        formatted = str(v).capitalize()
        if formatted not in allowed:
            raise ValueError(f"Structural Violation: Urgency/Priority must be one of {allowed}")
        return formatted

    @field_validator('assigned_tech', 'consumed_sku', 'manual_log', 'start_date', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

class MWOUpdate(BaseModel):
    status: Optional[str] = None
    consumed_sku: Optional[str] = None
    manual_log: Optional[str] = None
    assigned_tech: Optional[str] = None
    hm_priority: Optional[str] = None

    @field_validator('consumed_sku', 'manual_log', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

# --- SECURITY LAYER ---

def sanitize_user(user: dict) -> dict:
    """Strip pin_code from any user payload. Inject computed has_pin boolean."""
    has_pin = bool(user.get("pin_code"))
    sanitized = {k: v for k, v in user.items() if k != "pin_code"}
    sanitized["has_pin"] = has_pin
    return sanitized

def get_current_mwo(mwo_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path"
        cursor.execute(f"SELECT {cols} FROM work_orders WHERE mwo_id = ?", (mwo_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="MWO not found.")
        return dict(row)
    finally:
        conn.close()

def verify_rbac_pipeline(
    payload: MWOUpdate = Body(...), 
    current_mwo: dict = Depends(get_current_mwo),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return current_mwo

    role = jwt_payload.get("role")
    user_id = jwt_payload.get("sub")

    current_status = current_mwo.get("status")
    new_status = updates.get("status", current_status)

    if role == "ADMINISTRATOR":
        return current_mwo

    if role == "DM":
        allowed_keys = {"dm_urgency"}
        invalid_keys = set(updates.keys()) - allowed_keys
        if invalid_keys:
            raise HTTPException(status_code=403, detail=f"RBAC / Pipeline Violation for DM {user_id}")
        return current_mwo

    if role == "TECHNICIAN":
        allowed_keys = {"status", "manual_log"}
        invalid_keys = set(updates.keys()) - allowed_keys
        if invalid_keys:
            raise HTTPException(status_code=403, detail="RBAC / Pipeline Violation: Unauthorized mutation.")

        if "status" in updates and new_status != current_status:
            is_valid_transition = (
                (current_status == "ASSIGNED" and new_status == "IN_PROGRESS") or
                (current_status == "IN_PROGRESS" and new_status == "PENDING_REVIEW")
            )
            if not is_valid_transition:
                raise HTTPException(status_code=403, detail="RBAC / Pipeline Violation: Unauthorized mutation.")
        return current_mwo

    if role == "HM":
        allowed_keys = {"assigned_tech", "hm_priority", "status", "manual_log"} 
        invalid_keys = set(updates.keys()) - allowed_keys
        if invalid_keys:
            raise HTTPException(status_code=403, detail="RBAC / Pipeline Violation: Unauthorized mutation.")

        if "status" in updates and new_status != current_status:
            is_valid_transition = (
                (current_status == "UNASSIGNED" and new_status == "ASSIGNED") or
                (current_status == "PENDING_REVIEW" and new_status == "COMPLETED") or
                (new_status == "UNASSIGNED")
            )
            if not is_valid_transition:
                raise HTTPException(status_code=403, detail="RBAC / Pipeline Violation: Unauthorized mutation.")
        return current_mwo

    raise HTTPException(status_code=403, detail="RBAC / Pipeline Violation: Unauthorized mutation.")


# --- ENDPOINTS ---




@app.post("/api/user/refresh")
def refresh_token(request: Request):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh Token Missing.")
        
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=403, detail="Invalid Token Type.")
        if payload.get("jti") in REVOKED_JTIS:
            raise HTTPException(status_code=401, detail="Token Revoked (JTI Blacklisted).")
            
        user_id = payload.get("sub")
        role = payload.get("role")
        
        new_access_token = create_access_token(user_id=user_id, role=role)
        return {"status": "success", "access_token": new_access_token, "token_type": "bearer"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh Token Expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Cryptographic Verification Failed.")

# --- RATE LIMITER & CRYPTO ---
import bcrypt
import asyncio

MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 15

def verify_password_hash(plain_pin: str, hashed_pin: str) -> bool:
    """CPU-bound cryptographic task."""
    try:
        return bcrypt.checkpw(plain_pin.encode('utf-8'), hashed_pin.encode('utf-8'))
    except Exception:
        return False

def check_rate_limit(employee_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = int(time.time())
        cutoff = now - (LOCKOUT_WINDOW_MINUTES * 60)
        
        # Bounded read to avoid DB lock thrashing under brute force
        cursor.execute("SELECT COUNT(*) as attempt_count FROM auth_rate_limits WHERE employee_id = ? AND attempt_timestamp > ?", (employee_id, cutoff))
        row = cursor.fetchone()
        
        if row and row['attempt_count'] >= MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Account locked.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error during rate limit verification: {e}")
        raise HTTPException(status_code=500, detail="Security boundary enforcement failed.")
    finally:
        conn.close()

def record_failed_attempt(employee_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = int(time.time())
        cursor.execute("INSERT INTO auth_rate_limits (employee_id, attempt_timestamp) VALUES (?, ?)", (employee_id, now))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to record authentication anomaly: {e}")
    finally:
        conn.close()

def clear_failed_attempts(employee_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = int(time.time())
        cutoff = now - (LOCKOUT_WINDOW_MINUTES * 60)
        
        # Self-healing ledger pruning deferred to successful login
        cursor.execute("DELETE FROM auth_rate_limits WHERE attempt_timestamp < ?", (cutoff,))
        cursor.execute("DELETE FROM auth_rate_limits WHERE employee_id = ?", (employee_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to clear rate limit ledger: {e}")
    finally:
        conn.close()

@app.post("/api/user/authenticate")
async def authenticate_user(payload: PinVerify, response: Response):
    check_rate_limit(payload.employee_id)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Isolate query to ID only. DO NOT pass the raw PIN.
        query = '''
            SELECT e.id, e.name, e.authorization_level, e.pin_hash
            FROM erp_employees e
            WHERE e.id = ? AND e.is_active = 1
        '''
        cursor.execute(query, (payload.employee_id,))
        row = cursor.fetchone()
        
        if not row:
            record_failed_attempt(payload.employee_id)
            raise HTTPException(status_code=401, detail="Authorization Denied.")
            
        # Offload CPU-bound hash verification to thread pool to prevent ASGI blocking
        is_valid = await asyncio.to_thread(verify_password_hash, payload.pin, row["pin_hash"])
        
        if not is_valid:
            record_failed_attempt(payload.employee_id)
            raise HTTPException(status_code=401, detail="Authorization Denied.")
            
        # Clean up rate limit state for successful logins
        clear_failed_attempts(payload.employee_id)
            
        role = row["authorization_level"].upper()
        if role not in ["ADMIN", "ADMINISTRATOR", "DM", "HM", "TECHNICIAN", "TECH"]:
            raise HTTPException(status_code=500, detail="Invalid DB Role Mapping.")
        
        access_token = create_access_token(user_id=row["id"], role=role)
        refresh_token = create_refresh_token(user_id=row["id"], role=role)
        
        response.set_cookie(
            key="refresh_token", 
            value=refresh_token, 
            httponly=True, 
            secure=True, 
            samesite="Strict", 
            path="/api/user/refresh"
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 900
        }
    finally:
        if conn:
            conn.close()

# [PHASE 34.5 INJECTION] Provide HM routing matrix to the UI
@app.get("/api/admin/hms")
def get_hms(
    department: str = Query(..., description="Target department to filter HMs"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Strictly bounded parameterized query scoped to the exact department
        cursor.execute(
            """
            SELECT id, name 
            FROM erp_employees 
            WHERE authorization_level = 'HM' AND is_active = 1 AND department = ? 
            LIMIT ? OFFSET ?
            """,
            (department, limit, offset)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch bounded HM matrix: {e}")
        raise HTTPException(status_code=500, detail="Matrix synchronization failed.")
    finally:
        conn.close()

# [PHASE 34.5 INJECTION]
@app.post("/api/admin/ingest/single-user")
async def ingest_single_user(payload: EmployeeIngestionRecord, jwt_payload: dict = Depends(verify_jwt_token)):
    # 1. RBAC Adherence
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 2. CPU-Bound Password Hashing
        import bcrypt
        import asyncio
        pin_hash = await asyncio.to_thread(
            lambda p: bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), 
            payload.pin_code
        )
        
        # 3. Atomic Database Insertion
        cursor.execute(
            """
            INSERT INTO erp_employees (id, name, authorization_level, pin_code, pin_hash, is_active, department, reports_to_hm_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (payload.id, payload.name, payload.authorization_level, payload.pin_code, pin_hash, payload.is_active, payload.department, payload.reports_to_hm_id)
        )
        conn.commit()
        
        return {"status": "success", "message": f"Personnel {payload.id} successfully ingested."}
    except sqlite3.IntegrityError:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=409, detail="Structural Violation: Employee ID already exists.")
    except Exception as e:
        logger.error(f"Single Ingestion Error: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Internal Execution Error.")
    finally:
        if conn:
            conn.close()

# [PHASE 34.6 INJECTION]
@app.post("/api/admin/ingest/equipment")
def ingest_equipment(payload: EquipmentIngestionRecord, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO erp_equipment (equipment_id, nomenclature, category, status, department, assigned_tech_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (payload.equipment_id, payload.nomenclature, payload.category, payload.status, payload.department, payload.assigned_tech_id)
        )
        conn.commit()
        return {"status": "success", "message": f"Equipment {payload.equipment_id} successfully ingested."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Structural Violation: Equipment ID already exists.")
    except Exception as e:
        logger.error(f"Equipment Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Execution Error.")
    finally:
        conn.close()

@app.get("/api/admin/equipment")
def get_equipment(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    department: Optional[str] = Query(None, description="Optional filter by department"),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query_columns = "equipment_id, nomenclature, category, status, department, assigned_tech_id"
        if department:
            cursor.execute(
                f"SELECT {query_columns} FROM erp_equipment WHERE department = ? LIMIT ? OFFSET ?",
                (department, limit, offset)
            )
        else:
            cursor.execute(
                f"SELECT {query_columns} FROM erp_equipment LIMIT ? OFFSET ?",
                (limit, offset)
            )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch equipment matrix: {e}")
        raise HTTPException(status_code=500, detail="Matrix synchronization failed.")
    finally:
        conn.close()

@app.patch("/api/admin/equipment/{equipment_id}/status")
def update_equipment_status(equipment_id: str, payload: EquipmentStatusUpdate, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "DM", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Clearance required to actuate equipment state.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT equipment_id FROM erp_equipment WHERE equipment_id = ?", (equipment_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Equipment not found.")
            
        cursor.execute(
            "UPDATE erp_equipment SET status = ?, assigned_tech_id = ? WHERE equipment_id = ?",
            (payload.status, payload.assigned_tech_id, equipment_id)
        )
        conn.commit()
        return {"status": "success", "message": f"Equipment {equipment_id} state updated to {payload.status}."}
    except Exception as e:
        logger.error(f"Failed to update equipment status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")
    finally:
        conn.close()

@app.post("/api/admin/ingest/part")
def ingest_part(payload: PartIngestionRecord, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO erp_parts (part_id, nomenclature, category, quantity_on_hand, reorder_threshold, unit_cost)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (payload.part_id, payload.nomenclature, payload.category, payload.quantity_on_hand, payload.reorder_threshold, payload.unit_cost)
        )
        conn.commit()
        return {"status": "success", "message": f"Part {payload.part_id} successfully cataloged."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Structural Violation: Part ID already exists in the catalog.")
    except Exception as e:
        logger.error(f"Part Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Execution Error.")
    finally:
        conn.close()

@app.get("/api/admin/parts")
def get_parts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Explicit Column Enumeration Enforced
        cursor.execute(
            """
            SELECT part_id, nomenclature, category, quantity_on_hand, reorder_threshold, unit_cost 
            FROM erp_parts 
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch parts matrix: {e}")
        raise HTTPException(status_code=500, detail="Matrix synchronization failed.")
    finally:
        conn.close()

@app.post("/api/mwo/{mwo_id}/consume_part")
def consume_part(
    mwo_id: str, 
    payload: PartConsumptionPayload, 
    jwt_payload: dict = Depends(verify_jwt_token)
):
    tech_id = jwt_payload.get("sub")
    role = jwt_payload.get("role")
    
    if role not in ["ADMINISTRATOR", "ADMIN", "HM", "TECH"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Clearance required to actuate inventory.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Initiate Atomic Block
        cursor.execute("BEGIN TRANSACTION")

        # 1. State Validation: MWO Lockout Check
        cursor.execute("SELECT status FROM work_orders WHERE mwo_id = ?", (mwo_id,))
        mwo_state = cursor.fetchone()
        if not mwo_state:
            raise HTTPException(status_code=404, detail="MWO ledger entry not found.")
        if mwo_state['status'] == 'COMPLETED':
            raise HTTPException(status_code=400, detail="Structural Violation: Cannot allocate parts to a finalized MWO.")

        # 2. State Validation: Stock Verification
        cursor.execute("SELECT quantity_on_hand FROM erp_parts WHERE part_id = ?", (payload.part_id,))
        part_state = cursor.fetchone()
        if not part_state:
            raise HTTPException(status_code=404, detail="Part ID not found in master catalog.")
        if part_state['quantity_on_hand'] < payload.quantity_consumed:
            raise HTTPException(status_code=400, detail="Stock Violation: Insufficient physical inventory for allocation.")

        # 3. Actuation: Stock Depletion
        cursor.execute(
            "UPDATE erp_parts SET quantity_on_hand = quantity_on_hand - ? WHERE part_id = ?",
            (payload.quantity_consumed, payload.part_id)
        )

        # 4. Actuation: Append-Only Ledger Linkage
        txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        cursor.execute(
            """
            INSERT INTO erp_inventory_ledger (transaction_id, part_id, mwo_id, tech_id, quantity_consumed)
            VALUES (?, ?, ?, ?, ?)
            """,
            (txn_id, payload.part_id, mwo_id, tech_id, payload.quantity_consumed)
        )

        # Commit Atomic Block
        conn.commit()
        return {"status": "success", "message": f"Allocated {payload.quantity_consumed}x {payload.part_id} to {mwo_id}. Ledger ID: {txn_id}"}

    except HTTPException:
        conn.rollback() # Explicit Teardown
        raise
    except Exception as e:
        conn.rollback() # Explicit Teardown
        logger.error(f"Atomic Depletion Failure: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during inventory transaction.")
    finally:
        conn.close()

@app.get("/api/inventory/available")
def get_available_inventory(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    # Universal operational read access
    if role not in ["ADMINISTRATOR", "ADMIN", "HM", "TECH"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Invalid clearance.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Explicit Enumeration & Zero-Stock Exclusion Enforced
        cursor.execute(
            """
            SELECT part_id, nomenclature, quantity_on_hand 
            FROM erp_parts 
            WHERE quantity_on_hand > 0 
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Inventory extraction failed: {e}")
        raise HTTPException(status_code=500, detail="Catalog extraction error.")
    finally:
        conn.close()

@app.get("/api/system/directive")
def get_system_directive():
    """Exposes the Orchestration Boundary context to external agents."""
    if not GLOBAL_AI_DIRECTIVE_CONTEXT:
        raise HTTPException(status_code=503, detail="Directive context unavailable or not loaded.")
    return {"status": "success", "directive": GLOBAL_AI_DIRECTIVE_CONTEXT}

@app.get("/api/mwo/technicians")
def get_technicians(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Clearance required to view technician roster.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name FROM users WHERE role = 'TECH' AND is_active = 1")
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch technicians: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching technicians.")
    finally:
        conn.close()

@app.get("/api/mwo")
def get_mwo(limit: int = 50, offset: int = 0):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path"
        cursor.execute(
            f"SELECT {cols} FROM work_orders WHERE status = 'UNASSIGNED' ORDER BY execution_start DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch work orders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching work orders.")
    finally:
        if conn:
            conn.close()

async def archive_completed_mwo(mwo_data: dict):
    import asyncio
    queue_dir = "/app/archival_queue"
    os.makedirs(queue_dir, exist_ok=True)
    mwo_id = mwo_data.get("mwo_id", "UNKNOWN")
    
    archival_payload = {
        "document_type": "MWO_REPORT",
        "payload": mwo_data
    }
    
    tmp_path = os.path.join(queue_dir, f"{mwo_id}.tmp")
    final_path = os.path.join(queue_dir, f"{mwo_id}.json")
    
    def sync_archive():
        with open(tmp_path, 'w') as f:
            json.dump(archival_payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)
        
    await asyncio.to_thread(sync_archive)

def reconcile_inventory_ledger(mwo_id: str, consumed_sku: str):
    # REMOVED: async keyword (Forces Starlette threadpool delegation)
    # REMOVED: import asyncio
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Extract the unit_cost of the consumed SKU
        cursor.execute("SELECT stock_level, unit_cost FROM warehouse_inventory WHERE sku = ?", (consumed_sku,))
        row = cursor.fetchone()
        
        if not row:
            logger.warning(f"Reconciliation Failed: SKU '{consumed_sku}' not found in warehouse ledger.")
            return
            
        unit_cost = row['unit_cost']
        stock_level = row['stock_level']
        
        if stock_level <= 0:
            logger.warning(f"Reconciliation Warning: SKU '{consumed_sku}' stock level is already 0 or below.")
            
        # 2. Execute an UPDATE to decrement the stock_level by exactly 1
        cursor.execute("UPDATE warehouse_inventory SET stock_level = stock_level - 1 WHERE sku = ?", (consumed_sku,))
        
        # 3. Bind the operational drain directly to the MWO ledger record
        operational_drain = unit_cost * 1
        cursor.execute("UPDATE work_orders SET material_cost = ? WHERE mwo_id = ?", (operational_drain, mwo_id))
        
        # 4. Commit atomic transaction
        conn.commit()
        
        logger.info(f"Reconciliation Success [MWO: {mwo_id}]: SKU '{consumed_sku}' decremented. Ledger Updated: ${operational_drain:.2f}")
        
    except Exception as e:
        logger.error(f"Reconciliation Error [MWO: {mwo_id}]: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

@app.get("/api/mwo/assigned")
def get_assigned_mwo(limit: int = Query(50), offset: int = Query(0), jwt_payload: dict = Depends(verify_jwt_token)):
    user_id = jwt_payload.get("sub")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path"
        cursor.execute(
            f"SELECT {cols} FROM work_orders WHERE assigned_tech = ? AND status IN ('ASSIGNED', 'COMPLETED') ORDER BY mwo_id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch assigned work orders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching assigned work orders.")
    finally:
        if conn:
            conn.close()

class TechCompletePayload(BaseModel):
    consumed_sku: Optional[str] = None
    manual_log: str = Field(..., min_length=1)

def archive_mwo_pdf_worker(mwo_id: str):
    """
    [ASYNC ISOLATED WORKER]
    Target: CPU-Bound PDF Generation & I/O Archival
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        logger.info(f"[WORKER ENGAGED] Initiating asynchronous PDF archival for MWO: {mwo_id}")
        
        # 1. Explicit Data Extraction (Strict Enumeration)
        cursor.execute(
            """
            SELECT mwo_id, status, assigned_tech, manual_log 
            FROM work_orders 
            WHERE mwo_id = ?
            """, 
            (mwo_id,)
        )
        mwo_data = cursor.fetchone()
        
        if not mwo_data:
            logger.error(f"[WORKER FATAL] MWO {mwo_id} not found during archival extraction.")
            return

        # 2. Native Python PDF Byte-Compilation
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
        
        # Header
        pdf.set_font("helvetica", style="B", size=16)
        pdf.cell(0, 10, text=f"MAINTENANCE WORK ORDER ARCHIVE", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)
        
        # Payload Iteration
        pdf.set_font("helvetica", size=12)
        for key in mwo_data.keys():
            pdf.set_font("helvetica", style="B", size=12)
            pdf.cell(50, 10, text=f"{key.replace('_', ' ').upper()}:", new_x="RIGHT", new_y="TOP")
            
            pdf.set_font("helvetica", size=12)
            # Use multi_cell for unbounded text like manual_log
            pdf.multi_cell(0, 10, text=str(mwo_data[key]), new_x="LMARGIN", new_y="NEXT")

        # 3. Defensive Physical I/O Archival
        directory_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "archives/work_orders"))
        os.makedirs(directory_path, exist_ok=True)
        
        file_path = f"{directory_path}/{mwo_id}.pdf"
        pdf.output(file_path)
        logger.info(f"[WORKER I/O] Byte-compilation physically written to {file_path}")

        # 4. State Mutation (Schema Linkage)
        cursor.execute(
            "UPDATE work_orders SET archival_pdf_path = ? WHERE mwo_id = ?",
            (file_path, mwo_id)
        )
        conn.commit()
        logger.info(f"[WORKER SUCCESS] Archival cycle finalized for MWO: {mwo_id}")

    except Exception as e:
        logger.error(f"[WORKER FATAL] PDF Archival failed for MWO {mwo_id}: {e}")
    finally:
        conn.close()

@app.get("/api/mwo/{mwo_id}/archive")
def retrieve_mwo_archive(mwo_id: str, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    user_id = jwt_payload.get("sub")
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Explicit Enumeration & RBAC Retrieval
        cursor.execute(
            """
            SELECT assigned_tech, archival_pdf_path 
            FROM work_orders 
            WHERE mwo_id = ?
            """, 
            (mwo_id,)
        )
        record = cursor.fetchone()
        
        if not record:
            raise HTTPException(status_code=404, detail="MWO ledger entry not found.")
            
        if not record['archival_pdf_path']:
            raise HTTPException(status_code=404, detail="Archival payload has not been generated for this MWO.")

        # 2. Cryptographic Role Matrix Authorization
        if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
            # Strict Tech Validation: Must be the exactly assigned operator
            if role == "TECH" and record['assigned_tech'] != user_id:
                raise HTTPException(status_code=403, detail="RBAC Violation: You are not authorized to view this structural archive.")
            elif role not in ["TECH"]:
                 raise HTTPException(status_code=403, detail="RBAC Violation: Invalid role clearance.")

        # 3. Physical I/O Integrity Verification
        file_path = record['archival_pdf_path']
        if not os.path.exists(file_path):
            logger.error(f"[I/O FATAL] Schema points to missing physical volume: {file_path}")
            raise HTTPException(status_code=500, detail="Physical archival volume corrupted or missing.")

        # 4. Asynchronous File Stream Dispatch
        return FileResponse(
            path=file_path, 
            media_type="application/pdf", 
            filename=f"ARCHIVE_{mwo_id}.pdf"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Archive Retrieval Execution Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during stream initialization.")
    finally:
        conn.close()

@app.patch("/api/mwo/{mwo_id}/complete")
def complete_mwo(
    mwo_id: str, 
    payload: TechCompletePayload, 
    background_tasks: BackgroundTasks, 
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Clearance required to finalize MWO.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Optimal Existence & State Check
        cursor.execute("SELECT mwo_id, status FROM work_orders WHERE mwo_id = ?", (mwo_id,))
        mwo_record = cursor.fetchone()
        if not mwo_record:
            raise HTTPException(status_code=404, detail="MWO not found.")
        if mwo_record['status'] == 'COMPLETED':
            raise HTTPException(status_code=400, detail="MWO is already finalized.")
            
        # 2. State Mutation (Status -> COMPLETED)
        cursor.execute(
            "UPDATE work_orders SET status = 'COMPLETED', manual_log = ? WHERE mwo_id = ?",
            (payload.manual_log, mwo_id)
        )
        conn.commit()
        
        # 3. Asynchronous Thread Handoff
        background_tasks.add_task(archive_mwo_pdf_worker, mwo_id)
        
        return {
            "status": "success", 
            "message": f"MWO {mwo_id} finalized. PDF archival dispatched asynchronously."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MWO Completion Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")
    finally:
        conn.close()

@app.patch("/api/mwo/{mwo_id}")
async def update_mwo_v2(mwo_id: str, payload: MWOUpdate, background_tasks: BackgroundTasks, rbac_verified_mwo: dict = Depends(verify_rbac_pipeline)):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        current_time = datetime.now(timezone.utc).isoformat()
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            return {"status": "success", "message": "No changes provided"}
        
        # Guard: Terminal State Prerequisites (COMPLETED / APPROVED)
        # All three fields must be non-null and valid before terminal closure.
        target_status = update_data.get("status")
        if target_status in ("COMPLETED", "APPROVED"):
            cursor.execute("SELECT start_date, equipment_id, assigned_tech FROM work_orders WHERE mwo_id = ?", (mwo_id,))
            check_row = cursor.fetchone()
            if not check_row:
                raise HTTPException(status_code=404, detail=f"MWO {mwo_id} not found.")

            missing = []
            current_tech = check_row['assigned_tech']
            if not current_tech or current_tech.strip().upper() in ('', 'UNASSIGNED'):
                missing.append("assigned_tech")
            if not check_row['equipment_id']:
                missing.append("equipment_id")
            if not check_row['start_date']:
                missing.append("start_date")

            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot transition to {target_status}: missing prerequisites [{', '.join(missing)}]."
                )

            if target_status == "COMPLETED":
                update_data["completed_at"] = current_time

        # Guard: Start Date Injection
        if update_data.get("status") == "IN_PROGRESS":
            cursor.execute("SELECT start_date FROM work_orders WHERE mwo_id = ?", (mwo_id,))
            check_row = cursor.fetchone()
            if check_row and not check_row['start_date']:
                update_data["start_date"] = current_time

        # Dynamic SQL Generation
        columns = []
        values = []
        for key, value in update_data.items():
            columns.append(f"{key} = ?")
            values.append(value)
        
        sql = f"UPDATE work_orders SET {', '.join(columns)} WHERE mwo_id = ?"
        values.append(mwo_id)
        
        cursor.execute(sql, tuple(values))
        conn.commit()
        
        background_tasks.add_task(sync_memory_bus)
        
        # Terminal State Actuation: Atomic Drop Protocol
        if update_data.get("status") == "COMPLETED":
            cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path"
            cursor.execute(f"SELECT {cols} FROM work_orders WHERE mwo_id = ?", (mwo_id,))
            final_row = cursor.fetchone()
            if final_row:
                background_tasks.add_task(archive_completed_mwo, dict(final_row))
        
        return {"status": "success", "message": "MWO Updated successfully", "patch": update_data}
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Failed to update MWO {mwo_id}: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Internal server error while updating MWO.")
    finally:
        if conn:
            conn.close()

async def sync_memory_bus():
    import asyncio
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Fix 3: Query Safety (COLLATE NOCASE)
        cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path"
        cursor.execute(f"SELECT {cols} FROM work_orders WHERE status != 'COMPLETED' COLLATE NOCASE")
        raw_rows = [dict(row) for row in cursor.fetchall()]
        
        # Fix 1: The DTO Mapper
        mapped_rows = []
        for row in raw_rows:
            mapped_row = dict(row)
            if 'technician' in mapped_row:
                mapped_row['assigned_tech'] = mapped_row.pop('technician')
            if 'consumed_sku' in mapped_row:
                mapped_row['sku_consumed'] = mapped_row.pop('consumed_sku')
            mapped_rows.append(mapped_row)
        
        payload_data = {
            "agent_id": "MWO_Edge_Node",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "artifact_type": "Active_MWO_State",
            "payload": mapped_rows
        }
        
        shared_memory_dir = "/app/shared_memory"
        os.makedirs(shared_memory_dir, exist_ok=True)
        tmp_path = os.path.join(shared_memory_dir, "mwo_state_broadcast.tmp")
        final_path = os.path.join(shared_memory_dir, "mwo_state_broadcast.json")
        
        # Fix 2: Async I/O (Atomic Swap Protocol)
        def sync_write():
            with open(tmp_path, "w") as f:
                json.dump(payload_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, final_path)
                
        await asyncio.to_thread(sync_write)
    except Exception as e:
        logger.error(f"Failed to sync memory bus: {e}")
    finally:
        if conn:
            conn.close()

@app.post("/api/mwo/broadcast")
async def broadcast_mwo_state():
    await sync_memory_bus()
    return {"status": "success", "message": "Broadcast written to shared memory."}

@app.post("/api/orders/submit")
async def submit_order(order: WorkOrderSubmit):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Temporal Fix: Strict UTC ISO 8601 string
        reported_at = datetime.now(timezone.utc).isoformat()
        
        cursor.execute(
            """
            INSERT INTO erp_maintenance_logs 
            (reported_by, asset_id, issue_description, status, reported_at) 
            VALUES (?, ?, ?, ?, ?)
            RETURNING *
            """,
            (order.reported_by, order.asset_id, order.issue_description, "PENDING", reported_at)
        )
        
        inserted_row = cursor.fetchone()
        conn.commit()
        
        return {"status": "success", "data": [dict(inserted_row)]}
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Insert Failed: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed. Transaction rolled back.")
    finally:
        conn.close()

class AssignUpdate(BaseModel):
    order_id: str
    technician_id: str

@app.post("/api/orders/assign")
async def assign_order(payload: AssignUpdate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Optimistic Locking: Only update if not currently assigned
        cursor.execute(
            """
            UPDATE erp_maintenance_logs 
            SET assigned_to = ? 
            WHERE id = ? AND assigned_to IS NULL
            RETURNING *
            """,
            (payload.technician_id, payload.order_id)
        )
        
        # Concurrency Gate
        if cursor.rowcount == 0:
            conn.rollback()
            raise HTTPException(
                status_code=409, 
                detail="Conflict: Order is already assigned or does not exist."
            )
            
        assigned_row = cursor.fetchone()
        conn.commit()
        
        # Return array structure
        return [dict(assigned_row)]
        
    except HTTPException:
        raise  # Re-raise the 409 Conflict intentionally
    except Exception as e:
        conn.rollback()
        logger.error(f"Assign Failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during assignment.")
    finally:
        conn.close()



class NewMWO(BaseModel):
    mwo_id: Optional[str] = None
    description: str
    equipment_id: str
    location_id: str
    urgency: str
    assigned_tech: Optional[str] = None
    status: Optional[str] = "PENDING_REVIEW"

@app.post("/api/mwo")
async def create_mwo(payload: NewMWO):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        current_time = time.time()
        
        # Auto-generate ID if missing or empty
        final_mwo_id = payload.mwo_id
        if not final_mwo_id or not final_mwo_id.strip():
            cursor.execute("SELECT mwo_id FROM work_orders WHERE mwo_id LIKE 'MWO-%' ORDER BY mwo_id DESC LIMIT 1")
            last_record = cursor.fetchone()
            next_num = 1
            if last_record and last_record['mwo_id']:
                try:
                    # e.g. MWO-2026-003 -> 3
                    parts = last_record['mwo_id'].split('-')
                    if len(parts) >= 3:
                        last_num = int(parts[-1])
                        next_num = last_num + 1
                except ValueError:
                    pass
            current_year = datetime.now(timezone.utc).year
            final_mwo_id = f"MWO-{current_year}-{next_num:03d}"
            
        if not final_mwo_id or not final_mwo_id.strip():
            raise ValueError("Generated MWO ID is invalid.")

        cursor.execute(
            """
            INSERT INTO work_orders 
            (mwo_id, description, equipment_id, location_id, dm_urgency, assigned_tech, status, hm_priority, execution_start) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (final_mwo_id, payload.description, payload.equipment_id, payload.location_id, payload.urgency, payload.assigned_tech, "UNASSIGNED", "Normal", current_time)
        )
        conn.commit()
        
        # Fetch the newly created record
        cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path"
        cursor.execute(f"SELECT {cols} FROM work_orders WHERE mwo_id = ?", (final_mwo_id,))
        new_row = cursor.fetchone()
        
        return {"status": "success", "message": "MWO created successfully", "data": dict(new_row) if new_row else {}}
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create MWO: {e}")
        raise HTTPException(status_code=500, detail=str(e) or "Internal server error while creating MWO.")
    finally:
        conn.close()

import shutil
from pydantic import ValidationError
from typing import Literal

# STRICT SCHEMA ENFORCEMENT
class UserUploadSchema(BaseModel):
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    role: Literal['ADMIN', 'HD', 'HM', 'TECH']
    department: str
    reports_to_hm_id: Optional[str] = None

    @field_validator('reports_to_hm_id', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        return None if v == "" else v

def process_csv_background(file_path: str):
    conn = get_db_connection()
    # Enforce WAL mode for concurrent read/writes
    conn.execute("PRAGMA journal_mode=WAL;") 
    cursor = conn.cursor()
    
    try:
        rows_processed = 0
        errors = 0
        with open(file_path, mode='r', encoding='utf-8') as f:
            csv_reader = csv.DictReader(f)
            
            for raw_row in csv_reader:
                try:
                    # Rigorous Schema Validation before DB interaction
                    valid_row = UserUploadSchema(**raw_row)
                    
                    cursor.execute("""
                        INSERT INTO users (user_id, name, role, department, reports_to_hm_id)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            name=excluded.name,
                            role=excluded.role,
                            department=excluded.department,
                            reports_to_hm_id=excluded.reports_to_hm_id
                    """, (
                        valid_row.user_id,
                        valid_row.name,
                        valid_row.role,
                        valid_row.department,
                        valid_row.reports_to_hm_id
                    ))
                    rows_processed += 1
                except ValidationError as ve:
                    logger.error(f"Schema violation for row {raw_row}: {ve}")
                    errors += 1
                    continue # Skip invalid rows, do not crash batch
                except Exception as e:
                    logger.error(f"DB Error for row {raw_row}: {e}")
                    errors += 1
                    continue
                    
        conn.commit()
        logger.info(f"[BACKGROUND WORKER] CSV Ingestion Complete. Processed: {rows_processed}, Skipped: {errors}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Critical failure in background CSV processing: {e}")
    finally:
        conn.close()
        # Autonomous cleanup of temp file
        if os.path.exists(file_path):
            os.remove(file_path)


import concurrent.futures

def hash_pin_cpu_bound(pin: str) -> str:
    # Strictly CPU-bound bcrypt hashing
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pin.encode('utf-8'), salt).decode('utf-8')

def process_employee_csv_background(file_path: str):
    conn = get_db_connection()
    conn.execute("PRAGMA journal_mode=WAL;") 
    cursor = conn.cursor()
    
    try:
        rows_processed = 0
        errors = 0
        valid_records = []
        
        # Phase 1: I/O & Validation
        with open(file_path, mode='r', encoding='utf-8') as f:
            csv_reader = csv.DictReader(f)
            for raw_row in csv_reader:
                try:
                    record = EmployeeIngestionRecord(**raw_row)
                    valid_records.append(record)
                except Exception as ve:
                    logger.error(f"Schema violation for row: {ve}")
                    errors += 1
                    
        # Phase 2: CPU-Bound Hashing offloaded to ThreadPool
        hashed_records = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_record = {executor.submit(hash_pin_cpu_bound, r.pin_code): r for r in valid_records}
            for future in concurrent.futures.as_completed(future_to_record):
                record = future_to_record[future]
                try:
                    hashed_pin = future.result()
                    hashed_records.append((
                        record.id,
                        record.name,
                        record.authorization_level,
                        record.pin_code,  # Storing plain pin_code just for legacy structural alignment if required, but wait!
                        hashed_pin,
                        record.is_active
                    ))
                except Exception as e:
                    logger.error(f"Hashing failed for {record.id}: {e}")
                    errors += 1
                    
        # Phase 3: Atomic Batch SQLite Insertion
        if hashed_records:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.executemany("""
                INSERT INTO erp_employees (id, name, authorization_level, pin_code, pin_hash, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    authorization_level=excluded.authorization_level,
                    pin_code=excluded.pin_code,
                    pin_hash=excluded.pin_hash,
                    is_active=excluded.is_active
            """, hashed_records)
            conn.commit()
            rows_processed += len(hashed_records)
            
        logger.info(f"[BACKGROUND WORKER] Employee Ingestion Complete. Processed: {rows_processed}, Skipped: {errors}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Critical failure in employee background processing: {e}")
    finally:
        conn.close()
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/api/admin/employees/bulk-upload", status_code=202)
async def bulk_upload_employees(background_tasks: BackgroundTasks, jwt_payload: dict = Depends(verify_jwt_token), file: UploadFile = File(...)):
    if jwt_payload.get("role") not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: ADMIN clearance required.")
        
    if not file.filename.endswith((".csv", ".json")):
        raise HTTPException(status_code=400, detail="Strictly CSV/JSON payloads authorized.")
    
    tmp_path = f"/tmp/emp_{uuid.uuid4().hex}_{file.filename}"
    
    try:
        async with aiofiles.open(tmp_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  
                await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to write payload to temporary storage.")
    finally:
        await file.close()

    background_tasks.add_task(process_employee_csv_background, tmp_path)
    
    return {"status": "accepted", "message": "Employee payload queued for secure validation and processing."}

def validate_mwo_chunk(raw_chunk: list) -> tuple:
    valid = []
    errors = 0
    for raw_row in raw_chunk:
        try:
            r = MWOIngestionRecord(**raw_row)
            valid.append((
                r.mwo_id, r.status, r.dm_urgency, r.hm_priority,
                r.description, r.assigned_tech, r.consumed_sku,
                r.manual_log, 
                r.start_date.isoformat() if r.start_date else None, 
                r.equipment_id
            ))
        except Exception:
            errors += 1
    return valid, errors

def process_mwo_csv_background(file_path: str):
    try:
        rows_processed = 0
        errors = 0
        validated_batches = []
        chunk_size = 5000
        
        # Phase 1: CPU-Bound Decoupling with Strictly Streamed I/O
        with open(file_path, mode='r', encoding='utf-8') as f:
            csv_reader = csv.DictReader(f)
            
            with concurrent.futures.ProcessPoolExecutor() as executor:
                futures = []
                while True:
                    # Stream exactly 5000 rows into memory, preventing OOM
                    chunk = list(islice(csv_reader, chunk_size))
                    if not chunk:
                        break
                    futures.append(executor.submit(validate_mwo_chunk, chunk))
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        valid_batch, batch_errors = future.result()
                        errors += batch_errors
                        if valid_batch:
                            validated_batches.append(valid_batch)
                    except Exception as e:
                        logger.error(f"ProcessPool execution error: {e}")

        # Phase 2 & 3: Deferred DB Connection & Atomic Batch Write
        conn = get_db_connection()
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            for batch in validated_batches:
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                try:
                    cursor.executemany("""
                        INSERT INTO work_orders (
                            mwo_id, status, dm_urgency, hm_priority, description, 
                            assigned_tech, consumed_sku, manual_log, start_date, equipment_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(mwo_id) DO UPDATE SET
                            status=excluded.status,
                            dm_urgency=excluded.dm_urgency,
                            hm_priority=excluded.hm_priority,
                            description=excluded.description,
                            assigned_tech=excluded.assigned_tech,
                            consumed_sku=excluded.consumed_sku,
                            manual_log=excluded.manual_log,
                            start_date=excluded.start_date,
                            equipment_id=excluded.equipment_id
                    """, batch)
                    conn.commit()
                    rows_processed += len(batch)
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Batch write failure: {e}")
        finally:
            conn.close()
            
        logger.info(f"[BACKGROUND WORKER] Ingestion Complete. Processed: {rows_processed}, Skipped: {errors}")
        
    except Exception as e:
        logger.error(f"Critical failure in MWO processing: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/api/admin/mwo/bulk-upload", status_code=202)
async def bulk_upload_mwos(background_tasks: BackgroundTasks, jwt_payload: dict = Depends(verify_jwt_token), file: UploadFile = File(...)):
    if jwt_payload.get("role") not in ["ADMINISTRATOR", "ADMIN", "DM", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Insufficient clearance for bulk MWO ingestion.")
        
    if not file.filename.endswith((".csv", ".json")):
        raise HTTPException(status_code=400, detail="Strictly CSV/JSON payloads authorized.")
    
    tmp_path = f"/tmp/mwo_{uuid.uuid4().hex}_{file.filename}"
    
    try:
        async with aiofiles.open(tmp_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  
                await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to write payload to temporary storage.")
    finally:
        await file.close()

    background_tasks.add_task(process_mwo_csv_background, tmp_path)
    
    return {"status": "accepted", "message": "MWO payload queued for secure validation and processing."}

@app.post("/api/admin/users/bulk-upload", status_code=202)
async def bulk_upload_users(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Strictly CSV payloads authorized.")
    
    tmp_path = f"/tmp/{file.filename}"
    
    # Asynchronous chunked writing strictly prevents ASGI event loop blocking
    try:
        async with aiofiles.open(tmp_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to write payload to temporary storage.")
    finally:
        await file.close()

    # Offload strictly to background thread
    background_tasks.add_task(process_csv_background, tmp_path)
    
    return {"status": "accepted", "message": "Payload queued for validation and processing."}

@app.get("/api/orders/active")
async def get_active_orders():
    """
    Retrieves all non-closed maintenance work orders, ordered newest first.
    Strictly utilizes the new local SQLite adapter for concurrent stability.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                id,
                reported_by,
                asset_id,
                issue_description,
                status,
                assigned_to,
                resolved_at,
                reported_at
            FROM erp_maintenance_logs
            WHERE status != 'CLOSED'
            ORDER BY reported_at DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        orders = []
        for row in rows:
            orders.append({
                "id": row["id"],
                "reported_by": row["reported_by"],
                "asset_id": row["asset_id"],
                "issue_description": row["issue_description"],
                "status": row["status"],
                "assigned_to": row["assigned_to"],
                "resolved_at": row["resolved_at"],
                "reported_at": row["reported_at"]
            })
            
        return {"status": "success", "orders": orders}
        
    except Exception as e:
        logger.error(f"Active orders telemetry query failed: {e}")
        raise HTTPException(status_code=500, detail="Database Error: Unable to fetch active telemetry.")
        
    finally:
        if conn:
            conn.close()


@app.get("/api/admin/users")
async def get_admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    # Strict RBAC Enforcement
    actor_role = jwt_payload.get("role")
    if actor_role != "ADMIN":
        raise HTTPException(status_code=403, detail="RBAC Violation: ADMIN clearance required.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Mathematical SQLite Pagination
        offset = (page - 1) * limit
        
        # Enforce Soft Delete Boundary
        cursor.execute("""
            SELECT user_id, name, role, department, reports_to_hm_id, is_active
            FROM users
            WHERE is_active = 1
            ORDER BY user_id ASC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        
        # C-Optimized Serialization
        users = [{
            "user_id": row["user_id"],
            "name": row["name"],
            "role": row["role"],
            "department": row["department"],
            "reports_to_hm_id": row["reports_to_hm_id"],
            "is_active": row["is_active"]
        } for row in rows]
            
        return users
        
    except Exception as e:
        logger.error(f"Failed to fetch paginated matrix: {e}")
        raise HTTPException(status_code=500, detail="Database Error: Unable to fetch telemetry.")
    finally:
        if conn:
            conn.close()
            
@app.get("/api/admin/users/{user_id}/audit-log")
async def get_user_audit_log(
    user_id: str = Path(..., description="The target user's enterprise ID"),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    actor_role = jwt_payload.get("role")
    
    # Strict Taxonomy Validation
    if actor_role != "ADMIN":

        raise HTTPException(status_code=403, detail="RBAC Violation: ADMIN clearance required.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT event_id, target_user_id, actor_user_id, action_type, timestamp 
            FROM user_audit_logs 
            WHERE target_user_id = ? 
            ORDER BY timestamp DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        events = [{"event_id": r["event_id"], "target_user_id": r["target_user_id"], "actor_user_id": r["actor_user_id"], "action": r["action_type"], "timestamp": r["timestamp"]} for r in rows]
            
        return {"target_user_id": user_id, "events": events}
    except Exception as e:
        logger.error(f"Audit log retrieval failed for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contextual telemetry.")
    finally:
        conn.close()

@app.delete("/api/admin/users/{user_id}", status_code=204)
async def terminate_user_access(
    user_id: str = Path(..., description="The target user's enterprise ID to terminate"),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    actor_user_id = jwt_payload.get("sub")
    actor_role = jwt_payload.get("role")

    # Strict Taxonomy Validation
    if actor_role != "ADMIN":
        raise HTTPException(status_code=403, detail="RBAC Violation: ADMIN clearance required.")
        
    if actor_user_id == user_id:
        raise HTTPException(status_code=400, detail="Self-termination is architecturally prohibited.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Native Context Manager for Guaranteed Atomicity
        with conn:
            cursor.execute("SELECT is_active FROM users WHERE user_id = ?", (user_id,))
            target_user = cursor.fetchone()
            
            if not target_user:
                raise HTTPException(status_code=404, detail="Target user not found in the matrix.")
            if target_user["is_active"] == 0:
                raise HTTPException(status_code=400, detail="Target user is already structurally terminated.")
                
            cursor.execute("""
                UPDATE users 
                SET is_active = 0, token_version = token_version + 1 
                WHERE user_id = ?
            """, (user_id,))
            
            event_id = str(uuid.uuid4())
            action_type = "TERMINATE_ACCESS"
            
            cursor.execute("""
                INSERT INTO user_audit_logs (event_id, target_user_id, actor_user_id, action_type) 
                VALUES (?, ?, ?, ?)
            """, (event_id, user_id, actor_user_id, action_type))
            
        return None  
        
    except HTTPException:
        raise
    except sqlite3.Error as e:
        logger.error(f"Atomic transaction failed during structural termination: {e}")
        raise HTTPException(status_code=500, detail="Database constraints aborted the structural termination.")
    except Exception as e:
        logger.error(f"Unexpected error during termination sequence: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error aborted the actuation.")
    finally:
        conn.close()

class UserEscalationPayload(BaseModel):
    role: Literal['ADMIN', 'DM', 'HM', 'TECH']
    department: str

@app.put("/api/admin/users/{user_id}/escalate")
async def escalate_user(
    payload: UserEscalationPayload,
    response: Response,
    user_id: str = Path(..., description="The target user's enterprise ID"),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    actor_user_id = jwt_payload.get("sub")
    actor_role = jwt_payload.get("role")

    # Strict Taxonomy Validation
    if actor_role != "ADMIN":
        raise HTTPException(status_code=403, detail="RBAC Violation: ADMIN clearance required.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        
        cursor.execute("SELECT is_active FROM users WHERE user_id = ?", (user_id,))
        target_user = cursor.fetchone()
        
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found in the matrix.")
        if target_user["is_active"] == 0:
            raise HTTPException(status_code=400, detail="Target user is structurally terminated.")
            
        cursor.execute("""
            UPDATE users 
            SET role = ?, department = ?, token_version = token_version + 1 
            WHERE user_id = ?
        """, (payload.role, payload.department, user_id))
        
        event_id = str(uuid.uuid4())
        action_type = "ROLE_ESCALATION"
        
        cursor.execute("""
            INSERT INTO user_audit_logs (event_id, target_user_id, actor_user_id, action_type) 
            VALUES (?, ?, ?, ?)
        """, (event_id, user_id, actor_user_id, action_type))
        
        conn.commit()
        
        if actor_user_id == user_id:
            # Return specific flush signal for synchronous client-side JWT invalidation
            response.status_code = 205
            response.headers["X-Token-Flush"] = "true"
            return None
        else:
            return {"status": "success", "message": "Role escalation successful."}
        
    except HTTPException:
        conn.rollback()
        raise
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Atomic transaction failed during structural escalation: {e}")
        raise HTTPException(status_code=500, detail="Database constraints aborted the structural escalation.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Unexpected error during escalation sequence: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error aborted the actuation.")
    finally:
        conn.close()

# --- FRONTEND DEPLOYMENT ---
frontend_dist_path = os.path.join(_erp, 'maintenance_frontend', 'dist')

if os.path.exists(frontend_dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API Route Not Found")
            
        path = os.path.join(frontend_dist_path, full_path)
        if full_path and os.path.isfile(path):
            return FileResponse(path)
            
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))
