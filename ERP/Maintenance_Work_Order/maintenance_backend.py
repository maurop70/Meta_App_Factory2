import os
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
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
from fastapi import FastAPI, APIRouter, HTTPException, Query, UploadFile, File, BackgroundTasks, Header, Body, Depends, Security, Response, Path
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
import httpx
import asyncio

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from contextlib import asynccontextmanager

from local_db import get_db_connection
import os
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
from fpdf import FPDF

ALGORITHM = "RS256"
PUBLIC_KEY = None
security = HTTPBearer()

# Ingestion Logic for Orchestration Boundary
GLOBAL_AI_DIRECTIVE_CONTEXT = ""

# STRUCTURAL PATCH: Asynchronous boot context to prevent thread-locking
@asynccontextmanager
async def lifespan(app: FastAPI):
    global PUBLIC_KEY
    global GLOBAL_AI_DIRECTIVE_CONTEXT
    
    # Load Orchestration Boundary
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

    # NGINX DOCTRINE: Trailing slash strictly enforced
    url = "http://127.0.0.1:9000/api/v1/auth/public-key" 
    
    async with httpx.AsyncClient() as client:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = await client.get(url, timeout=5.0, follow_redirects=True)
                response.raise_for_status()
                PUBLIC_KEY = response.json()["public_key"]
                logger.info("[SECURITY] Successfully fetched RS256 Public Key from Module 0 Gateway.")
                break
            except Exception as e:
                logger.warning(f"[SECURITY] Gateway fetch failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise RuntimeError("FATAL: Could not retrieve PUBLIC_KEY from Module 0 Gateway.")
    yield
    # Application teardown logic executes here

app = FastAPI(title="Maintenance Work Order API - Global ERP Connected", lifespan=lifespan)
api_router = APIRouter(prefix="/api")

def is_jti_revoked(jti: str) -> bool:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
        return row is not None
    except Exception as e:
        logger.error(f"Failed to check JTI status: {e}")
        return False
    finally:
        conn.close()

def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    if not PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Cryptographic Gateway Unavailable.")
        
    token = credentials.credentials
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        
        # JTI check routed to persistent storage
        if is_jti_revoked(payload.get("jti")):
            raise HTTPException(status_code=401, detail="Token Revoked (JTI Blacklisted).")
            
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token Expired.")
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT Verification Error: {str(e)}")
        raise HTTPException(status_code=403, detail="Cryptographic Verification Failed.")

# Serve frontend is deprecated due to NGINX Reverse-Proxy Decoupling Doctrine

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
    nomenclature: str = Field(..., min_length=2, description="Human-readable equipment name")
    category_id: str = Field(..., description="FK reference to erp_categories.id")
    status: str = Field(default="ACTIVE", description="Strictly enforced operational state")
    department_id: str = Field(..., description="FK reference to erp_departments.id")
    assigned_tech_id: Optional[str] = None
    location_id: str = Field(..., description="Physical location tag")
    assigned_hm_id: str = Field(..., description="Hub Manager assigned to this equipment")
    
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

class EquipmentActuationPayload(BaseModel):
    status: str = Field(..., description="ACTIVE, DEGRADED, OFFLINE, RETIRED")
    assigned_tech_id: Optional[str] = None

    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v):
        allowed_states = {"ACTIVE", "DEGRADED", "OFFLINE", "RETIRED"}
        if str(v).upper() not in allowed_states:
            raise ValueError(f"Structural Violation: Status must be one of {allowed_states}")
        return str(v).upper()

    @field_validator('assigned_tech_id', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

class EmployeeIngestionRecord(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    role: str = Field(..., description="Mapped Role (e.g., ADMIN, TECH)")
    pin_code: str = Field(..., min_length=4, max_length=12, description="Raw PIN to be hashed")
    is_active: int = Field(default=1, ge=0, le=1)
    
    # [PHASE 35.3 RELATIONAL INJECTIONS]
    department_id: str = Field(..., min_length=2, description="Physical operational department FK")
    reports_to_hm_id: Optional[str] = None
    
    @field_validator('role', mode='before')
    @classmethod
    def validate_role(cls, v):
        allowed = {"ADMINISTRATOR", "ADMIN", "HM", "TECH"}
        if str(v).upper() not in allowed:
            raise ValueError(f"Structural Violation: Role must be one of {allowed}")
        return str(v).upper()
    
    @field_validator('reports_to_hm_id', mode='after')
    @classmethod
    def require_hm_for_tech(cls, v, info):
        role = info.data.get('role', '').upper()
        if role in ["TECH", "TECHNICIAN"] and not v:
            raise ValueError("Structural Violation: A TECHNICIAN must be assigned a reporting HM.")
        return v

# [PHASE 34.9] Parts Catalog Ingestion Schema
class PartIngestionRecord(BaseModel):
    nomenclature: str = Field(..., min_length=2, description="Human-readable part name")
    category_id: str = Field(..., description="Foreign Key to erp_categories")
    quantity_on_hand: int = Field(default=0, ge=0, description="Initial physical stock count")
    reorder_threshold: int = Field(default=5, ge=0, description="Minimum threshold before alert")
    unit_cost: float = Field(default=0.0, ge=0.0, description="Financial cost per unit")

from typing import List

class MwoConsumptionPayload(BaseModel):
    part_ids: List[str] = Field(..., min_items=1, description="Array of exact physical part identifiers")

class PartConsumptionPayload(BaseModel):
    part_id: str = Field(..., description="The physical part identifier from erp_parts")
    quantity_consumed: int = Field(..., gt=0, description="Strictly positive integer")

class SKUCreate(BaseModel):
    sku_id: str
    nomenclature: str
    unit_cost: float
    reorder_threshold: int

class PartCreate(BaseModel):
    sku_id: str
    serial_number: Optional[str] = None

class PartResponse(BaseModel):
    part_id: str
    sku_id: str
    serial_number: Optional[str]
    status: str

class InventoryMutation(BaseModel):
    sku_id: str
    mutation_type: str = Field(..., description="IN or OUT")
    quantity: int

    @field_validator('mutation_type')
    @classmethod
    def validate_mutation(cls, v):
        if str(v).upper() not in ["IN", "OUT"]:
            raise ValueError("mutation_type must be IN or OUT")
        return str(v).upper()

class ProcurementActuation(BaseModel):
    status: str = Field(..., description="Target state: APPROVED, REJECTED, or FULFILLED")
    authorized_quantity: Optional[int] = Field(default=None, ge=1, description="Required only when status is APPROVED")

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
        allowed_states = {"UNASSIGNED", "ASSIGNED", "IN_PROGRESS", "PAUSED", "PENDING_REVIEW", "COMPLETED"}
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
    manual_log: Optional[str] = None
    assigned_tech: Optional[str] = None
    hm_priority: Optional[str] = None

    @field_validator('manual_log', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

class MWOExecutePayload(BaseModel):
    action: str = Field(..., description="START, PAUSE, COMPLETE")
    manual_log: Optional[str] = None

    @field_validator('action', mode='before')
    @classmethod
    def validate_action(cls, v):
        allowed = {"START", "PAUSE", "COMPLETE"}
        if str(v).upper() not in allowed:
            raise ValueError(f"Action must be one of {allowed}")
        return str(v).upper()

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
    current_status = current_mwo.get("status")
    new_status = updates.get("status", current_status)
    
    if role == "ADMINISTRATOR":
        return current_mwo
        
    if role == "DM":
        if not set(updates.keys()).issubset({"dm_urgency"}):
            raise HTTPException(status_code=403, detail="RBAC Violation: DM unauthorized mutation.")
        return current_mwo
        
    if role == "TECHNICIAN":
        if not set(updates.keys()).issubset({"status", "manual_log"}):
            raise HTTPException(status_code=403, detail="RBAC Violation: Technician unauthorized mutation.")
            
        if new_status != current_status:
            if not ((current_status == "ASSIGNED" and new_status == "IN_PROGRESS") or
                    (current_status == "IN_PROGRESS" and new_status == "PENDING_REVIEW")):
                raise HTTPException(status_code=403, detail="RBAC Violation: Invalid pipeline transition.")
        return current_mwo
        
    if role == "HM":
        if not set(updates.keys()).issubset({"assigned_tech", "hm_priority", "status", "manual_log"}):
            raise HTTPException(status_code=403, detail="RBAC Violation: HM unauthorized mutation.")
            
        if new_status != current_status:
            if not ((current_status == "UNASSIGNED" and new_status == "ASSIGNED") or
                    (current_status == "PENDING_REVIEW" and new_status == "COMPLETED") or
                    (new_status == "UNASSIGNED")):
                raise HTTPException(status_code=403, detail="RBAC Violation: Invalid pipeline transition.")
        return current_mwo
        
    raise HTTPException(status_code=403, detail="RBAC / Pipeline Violation: Unrecognized role.")


# --- ENDPOINTS ---




# Authentication and Identity management (including login, refresh, and rate limiting)
# have been fully delegated to the Module 0 Gateway on port 9000.

# [PHASE 34.5 INJECTION] Provide HM routing matrix to the UI
@api_router.get("/admin/hms")
def get_hms(
    department_id: str = Query(..., description="Target department ID to filter HMs"),
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
            WHERE role = 'HM' AND is_active = 1 AND department_id = ? 
            LIMIT ? OFFSET ?
            """,
            (department_id, limit, offset)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch bounded HM matrix: {e}")
        raise HTTPException(status_code=500, detail="Matrix synchronization failed.")
    finally:
        conn.close()

# [PHASE 34.5 INJECTION]
@api_router.post("/admin/ingest/single-user")
async def ingest_single_user(payload: EmployeeIngestionRecord, jwt_payload: dict = Depends(verify_jwt_token)):
    # 1. RBAC Adherence
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
        
    # Mandatory Silent Patch: Explicit Route-Level Validation
    if payload.role == 'TECH' and not payload.reports_to_hm_id:
        raise HTTPException(status_code=400, detail="Structural Violation: TECH must be bound to a reporting HM.")
        
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
        
        # 3. PK Synthesization
        import uuid
        new_id = f"U-{uuid.uuid4().hex[:6].upper()}"
        
        # 4. Atomic Database Insertion (Cryptographic isolation - NO plaintext pin_code)
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            """
            INSERT INTO erp_employees (id, name, role, pin_hash, is_active, department_id, reports_to_hm_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id, payload.name, payload.role, pin_hash, payload.is_active, payload.department_id, payload.reports_to_hm_id)
        )
        conn.commit()
        
        return {"status": "success", "message": f"Personnel {new_id} successfully ingested."}
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

# [PHASE 35.1 INJECTION — FK-NORMALIZED]
@api_router.post("/admin/ingest/equipment")
def ingest_equipment(payload: EquipmentIngestionRecord, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
        
    # Autonomously generate PK — operators never dictate physical keys
    equipment_id = f"EQ-{uuid.uuid4().hex[:6].upper()}"

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            """
            INSERT INTO erp_equipment (equipment_id, nomenclature, category_id, status, department_id, assigned_tech_id, location_id, assigned_hm_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (equipment_id, payload.nomenclature, payload.category_id, payload.status, payload.department_id, payload.assigned_tech_id, payload.location_id, payload.assigned_hm_id)
        )
        conn.commit()
        return {"status": "success", "message": f"Equipment {equipment_id} successfully ingested.", "equipment_id": equipment_id}
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"Structural Violation: FK constraint or duplicate key. {e}")
    except Exception as e:
        logger.error(f"Equipment Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Execution Error.")
    finally:
        conn.close()


def generate_xlsx_template(headers, template_name, categories=[], departments=[], locations=[], hms=[], techs=[]):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ingestion_Template"
    
    for col_idx, header in enumerate(headers, 1):
        ws.cell(row=1, column=col_idx, value=header)
        
    lookup_ws = wb.create_sheet(title="_Lookups")
    lookup_ws.sheet_state = 'hidden'
    
    current_col = 1
    def add_lookup_col(name, items):
        nonlocal current_col
        lookup_ws.cell(row=1, column=current_col, value=name)
        for r_idx, item in enumerate(items, 2):
            lookup_ws.cell(row=r_idx, column=current_col, value=item)
        col_letter = openpyxl.utils.get_column_letter(current_col)
        formula = f"=_Lookups!${col_letter}$2:${col_letter}${len(items)+1 if len(items)>0 else 2}"
        current_col += 1
        return formula

    if "category_name" in headers and categories:
        form = add_lookup_col("Categories", categories)
        dv = DataValidation(type="list", formula1=form, allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("category_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "department_name" in headers and departments:
        form = add_lookup_col("Departments", departments)
        dv = DataValidation(type="list", formula1=form, allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("department_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "location" in headers and locations:
        form = add_lookup_col("Locations", locations)
        dv = DataValidation(type="list", formula1=form, allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("location") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "hm_name" in headers and hms:
        form = add_lookup_col("HMs", hms)
        dv = DataValidation(type="list", formula1=form, allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("hm_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "reports_to_hm_name" in headers and hms:
        form = add_lookup_col("HMs", hms)
        dv = DataValidation(type="list", formula1=form, allow_blank=True)
        col_letter = openpyxl.utils.get_column_letter(headers.index("reports_to_hm_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "tech_name" in headers and techs:
        form = add_lookup_col("Techs", techs)
        dv = DataValidation(type="list", formula1=form, allow_blank=True)
        col_letter = openpyxl.utils.get_column_letter(headers.index("tech_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "status" in headers:
        dv = DataValidation(type="list", formula1='"ACTIVE,DEGRADED,OFFLINE"', allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("status") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)

    if "role" in headers:
        dv = DataValidation(type="list", formula1='"ADMINISTRATOR,ADMIN,DM,HM,TECH"', allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("role") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={template_name}.xlsx"}
    )

# [PHASE 35.1.1] Bulk CSV Ingestion Endpoints
@api_router.get("/admin/ingest/equipment/template")
def get_equipment_ingestion_template(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM erp_categories")
        categories = [row['name'] for row in c.fetchall()]
        c.execute("SELECT name FROM erp_departments")
        departments = [row['name'] for row in c.fetchall()]
        c.execute("SELECT name FROM erp_locations")
        locations = [row['name'] for row in c.fetchall()]
        c.execute("SELECT name FROM erp_employees WHERE role='HM'")
        hms = [row['name'] for row in c.fetchall()]
    finally:
        conn.close()
        
    headers = ["nomenclature", "category_name", "status", "department_name", "location", "hm_name"]
    return generate_xlsx_template(headers, "equipment_ingestion_template", categories, departments, locations, hms)

@api_router.post("/admin/ingest/equipment/bulk")
async def bulk_ingest_equipment(file: UploadFile = File(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
        
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an XLSX file.")
        
    content = await file.read()
    try:
        wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
        ws = wb.active
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        if not header_row: raise ValueError("Empty file")
        expected_fields = {"nomenclature", "category_name", "status", "department_name", "location", "hm_name"}
        if not expected_fields.issubset(set(header_row)):
            raise HTTPException(status_code=400, detail=f"Invalid XLSX structure. Expected minimum headers: {', '.join(expected_fields)}")
        rows = []
        for row_values in ws.iter_rows(min_row=2, values_only=True):
            if not any(row_values): continue
            row_dict = dict(zip(header_row, row_values))
            rows.append(row_dict)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read XLSX: {e}")
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Pre-fetch lookup mappings to avoid N+1 queries
        cursor.execute("SELECT id, name FROM erp_categories")
        cat_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT id, name FROM erp_departments")
        dep_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT id, name FROM erp_locations")
        loc_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT id, name FROM erp_employees WHERE role = 'HM'")
        hm_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}

        cursor.execute("BEGIN TRANSACTION")
        
        inserted_count = 0
        for i, row in enumerate(rows):
            # Clean up keys and values
            row_data = {k.strip(): str(v).strip() if v is not None else None for k, v in row.items()}
            
            # Resolve Names to IDs
            cat_name = row_data.get('category_name')
            if not cat_name:
                raise ValueError(f"Row {i+2}: Missing category_name")
            if cat_name.lower() not in cat_map:
                new_cat = f"CAT-{uuid.uuid4().hex[:6].upper()}"
                cursor.execute("INSERT INTO erp_categories (id, name) VALUES (?, ?)", (new_cat, cat_name.strip()))
                cat_map[cat_name.lower()] = new_cat
            cat_id = cat_map[cat_name.lower()]
                
            dep_name = row_data.get('department_name')
            if not dep_name:
                raise ValueError(f"Row {i+2}: Missing department_name")
            if dep_name.lower() not in dep_map:
                new_dep = f"DEP-{uuid.uuid4().hex[:6].upper()}"
                cursor.execute("INSERT INTO erp_departments (id, name) VALUES (?, ?)", (new_dep, dep_name.strip()))
                dep_map[dep_name.lower()] = new_dep
            dep_id = dep_map[dep_name.lower()]
            
            hm_name = row_data.get('hm_name')
            if not hm_name or hm_name.lower() not in hm_map:
                raise ValueError(f"Row {i+2}: Unknown HM Name '{hm_name}'")
            hm_id = hm_map[hm_name.lower()]
            
            loc_name = row_data.get('location')
            if not loc_name:
                raise ValueError(f"Row {i+2}: Missing location")
            if loc_name.lower() not in loc_map:
                new_loc = f"LOC-{uuid.uuid4().hex[:6].upper()}"
                cursor.execute("INSERT INTO erp_locations (id, name) VALUES (?, ?)", (new_loc, loc_name.strip()))
                loc_map[loc_name.lower()] = new_loc
            loc_id = loc_map[loc_name.lower()]
            
            # Autonomously generate PK
            equipment_id = f"EQ-{uuid.uuid4().hex[:6].upper()}"
            
            # Status validation
            status = row_data.get('status', 'ACTIVE') or 'ACTIVE'
            status = status.upper()
            if status not in {"ACTIVE", "DEGRADED", "OFFLINE"}:
                raise ValueError(f"Row {i+2}: Status must be ACTIVE, DEGRADED, or OFFLINE.")
                
            cursor.execute(
                """
                INSERT INTO erp_equipment (equipment_id, nomenclature, category_id, status, department_id, location_id, assigned_hm_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    equipment_id, 
                    row_data.get('nomenclature'), 
                    cat_id, 
                    status, 
                    dep_id, 
                    loc_id, 
                    hm_id
                )
            )
            inserted_count += 1
            
        conn.commit()
        return {"status": "success", "message": f"Successfully ingested {inserted_count} equipment records."}
        
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=f"Structural Violation on bulk insert. {e}")
    except ValueError as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        conn.rollback()
        logger.error(f"Bulk Equipment Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Execution Error during bulk ingestion.")
    finally:
        conn.close()

@api_router.get("/admin/equipment")
def get_equipment(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    department_id: Optional[str] = Query(None, description="Optional filter by department FK"),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        base_query = """
            SELECT e.equipment_id, e.nomenclature, e.category_id, c.name AS category,
                   e.status, e.department_id, d.name AS department, e.assigned_tech_id,
                   e.location_id, l.name AS location_name
            FROM erp_equipment e
            LEFT JOIN erp_categories c ON e.category_id = c.id
            LEFT JOIN erp_departments d ON e.department_id = d.id
            LEFT JOIN erp_locations l ON e.location_id = l.id
        """
        if department_id:
            cursor.execute(
                f"{base_query} WHERE e.department_id = ? LIMIT ? OFFSET ?",
                (department_id, limit, offset)
            )
        else:
            cursor.execute(
                f"{base_query} LIMIT ? OFFSET ?",
                (limit, offset)
            )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch equipment matrix: {e}")
        raise HTTPException(status_code=500, detail="Matrix synchronization failed.")
    finally:
        conn.close()

# [PHASE 35.1] Paginated Lookup Routes
@api_router.get("/admin/lookups/categories")
def get_categories(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM erp_categories ORDER BY name LIMIT ? OFFSET ?", (limit, offset))
        return {"data": [dict(r) for r in cursor.fetchall()]}
    finally:
        conn.close()

@api_router.get("/admin/lookups/departments")
def get_departments(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM erp_departments ORDER BY name LIMIT ? OFFSET ?", (limit, offset))
        return {"data": [dict(r) for r in cursor.fetchall()]}
    finally:
        conn.close()

@api_router.get("/admin/lookups/locations")
def get_locations(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM erp_locations ORDER BY name LIMIT ? OFFSET ?", (limit, offset))
        return {"data": [dict(r) for r in cursor.fetchall()]}
    finally:
        conn.close()

@api_router.post("/admin/ingest/department")
def ingest_department(payload: dict = Body(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
    name = payload.get("name")
    if not name or len(name) < 2:
        raise HTTPException(status_code=400, detail="Invalid department name")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        import uuid
        new_id = f"DEP-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("INSERT INTO erp_departments (id, name) VALUES (?, ?)", (new_id, name))
        conn.commit()
        return {"status": "success", "id": new_id, "name": name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Department already exists")
    finally:
        conn.close()

@api_router.post("/admin/ingest/location")
def ingest_location(payload: dict = Body(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
    name = payload.get("name")
    if not name or len(name) < 2:
        raise HTTPException(status_code=400, detail="Invalid location name")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        import uuid
        new_id = f"LOC-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("INSERT INTO erp_locations (id, name) VALUES (?, ?)", (new_id, name))
        conn.commit()
        return {"status": "success", "id": new_id, "name": name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Location already exists")
    finally:
        conn.close()

@api_router.get("/admin/lookups/technicians")
def get_technicians(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name FROM erp_employees WHERE authorization_level = 'TECHNICIAN' AND is_active = 1 ORDER BY name LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return {"data": [dict(r) for r in cursor.fetchall()]}
    finally:
        conn.close()

# [PHASE 35.2] Equipment Actuation Gateway
@api_router.put("/admin/equipment/{equipment_id}/actuate")
def actuate_equipment(
    equipment_id: str,
    payload: EquipmentActuationPayload,
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: ADMIN or HM clearance required to actuate equipment.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("BEGIN TRANSACTION")
        
        # 1. Existence + Current State Check
        cursor.execute(
            "SELECT equipment_id, status, assigned_tech_id FROM erp_equipment WHERE equipment_id = ?",
            (equipment_id,)
        )
        record = cursor.fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="Equipment not found.")
        
        # 2. RETIRED Immutability: Once retired, no further mutations
        if record['status'] == 'RETIRED':
            raise HTTPException(status_code=400, detail="Structural Violation: RETIRED equipment is permanently locked.")
        
        # 3. If retiring, clear tech assignment (equipment removed from service)
        tech_id = payload.assigned_tech_id
        if payload.status == 'RETIRED':
            tech_id = None
        
        # 4. Mutation
        cursor.execute(
            "UPDATE erp_equipment SET status = ?, assigned_tech_id = ? WHERE equipment_id = ?",
            (payload.status, tech_id, equipment_id)
        )
        conn.commit()
        
        return {
            "status": "success",
            "message": f"Equipment {equipment_id} actuated to {payload.status}.",
            "retired": payload.status == 'RETIRED'
        }
    except HTTPException:
        conn.rollback()
        raise
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=f"FK Violation: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Equipment Actuation Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")
    finally:
        conn.close()

@api_router.post("/admin/ingest/part")
def ingest_part(payload: PartIngestionRecord, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # PK Synthesization
        import uuid
        new_id = f"PRT-{uuid.uuid4().hex[:6].upper()}"
        
        # Enforce Relational Integrity
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            """
            INSERT INTO erp_parts (part_id, nomenclature, category_id, quantity_on_hand, reorder_threshold, unit_cost)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (new_id, payload.nomenclature, payload.category_id, payload.quantity_on_hand, payload.reorder_threshold, payload.unit_cost)
        )
        conn.commit()
        return {"status": "success", "message": f"Part {new_id} successfully cataloged."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Structural Violation: Relational boundary mismatch or nomenclature uniqueness conflict.")
    except Exception as e:
        logger.error(f"Part Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Execution Error.")
    finally:
        conn.close()

@api_router.get("/admin/parts")
def get_parts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.part_id, p.nomenclature, c.name as category, p.quantity_on_hand, p.reorder_threshold, p.unit_cost 
            FROM erp_parts p
            LEFT JOIN erp_categories c ON p.category_id = c.id
            ORDER BY p.part_id ASC
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

from datetime import datetime, timezone

def worker_evaluate_threshold(part_id: str):
    """
    Strictly isolated asynchronous threshold evaluation worker.
    Executes outside the HTTP response cycle.
    """
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        
        # 1. Evaluate Threshold Boundary
        c.execute("""
            SELECT s.quantity_on_hand, s.reorder_threshold 
            FROM erp_parts p 
            JOIN erp_skus s ON p.sku_id = s.sku_id 
            WHERE p.part_id = ?
        """, (part_id,))
        part = c.fetchone()
        
        if not part:
            logger.error(f"[WORKER TERMINATION] part_id {part_id} not found in physical ledger.")
            return
            
        if part['quantity_on_hand'] > part['reorder_threshold']:
            # Threshold not breached. Silently terminate CPU cycle.
            return
            
        # 2. Logical Concurrency Check (Save UUID generation and INSERT overhead)
        c.execute("""
            SELECT procurement_id FROM erp_procurement_queue 
            WHERE part_id = ? AND status IN ('PENDING', 'APPROVED')
        """, (part_id,))
        
        if c.fetchone():
            # Active procurement cycle already exists. Prevent supply chain spam.
            logger.info(f"[WORKER TERMINATION] Active procurement already queued for {part_id}.")
            return
            
        # 3. Payload Synthesization
        procurement_id = f"PROC-{uuid.uuid4().hex[:6].upper()}"
        triggered_at = datetime.now(timezone.utc).isoformat()
        
        # 4. Atomic Insertion
        c.execute("""
            INSERT INTO erp_procurement_queue (procurement_id, part_id, triggered_at, status)
            VALUES (?, ?, ?, 'PENDING')
        """, (procurement_id, part_id, triggered_at))
        
        conn.commit()
        logger.warning(f"[ACTUATION ENGAGED] Low Stock Alert: {procurement_id} queued for {part_id}.")
        
    except sqlite3.IntegrityError as e:
        # The partial index intercepted a race condition spanning the logical check.
        conn.rollback()
        logger.info(f"[CONCURRENCY LOCK ENGAGED] Redundant procurement blocked for {part_id}: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"[FATAL WORKER EXCEPTION] Evaluation failed for {part_id}: {e}")
    finally:
        conn.close()


@api_router.get("/inventory/available")
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
            SELECT p.part_id, s.nomenclature, s.quantity_on_hand 
            FROM erp_parts p
            JOIN erp_skus s ON p.sku_id = s.sku_id
            WHERE p.status = 'IN_STOCK' AND s.quantity_on_hand > 0 
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Inventory extraction failed: {e}")
        raise HTTPException(status_code=500, detail="Catalog extraction error.")
# [PHASE 37] Procurement Authorization Matrix

@api_router.put("/admin/procurement/{procurement_id}/actuate")
def actuate_procurement(
    procurement_id: str,
    payload: ProcurementActuation,
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
        
    if payload.status not in ["APPROVED", "REJECTED", "FULFILLED"]:
        raise HTTPException(status_code=400, detail="Invalid target status.")
        
    if payload.status == "APPROVED" and not payload.authorized_quantity:
        raise HTTPException(status_code=400, detail="Structural Violation: APPROVED state requires an authorized_quantity.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Escalate to immediate write-lock to prevent read-modify-write race conditions
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        
        cursor.execute("SELECT status, part_id, authorized_quantity FROM erp_procurement_queue WHERE procurement_id = ?", (procurement_id,))
        record = cursor.fetchone()
        
        if not record:
            raise HTTPException(status_code=404, detail="Procurement record not found.")
            
        current_status = record["status"]
        part_id = record["part_id"]
        
        cursor.execute("SELECT sku_id FROM erp_parts WHERE part_id = ?", (part_id,))
        sku_record = cursor.fetchone()
        if not sku_record:
            raise HTTPException(status_code=500, detail="Fatal execution error: part_id in procurement queue does not map to a valid sku_id.")
        sku_id = sku_record["sku_id"]
        
        db_authorized_qty = record["authorized_quantity"]
        
        # State Machine Enforcement
        if current_status in ["REJECTED", "FULFILLED"]:
            raise HTTPException(status_code=400, detail=f"Terminal State Violation: Cannot transition from {current_status}.")
        if current_status == "PENDING" and payload.status not in ["APPROVED", "REJECTED"]:
            raise HTTPException(status_code=400, detail=f"State Violation: PENDING shifts to APPROVED or REJECTED.")
        if current_status == "APPROVED" and payload.status != "FULFILLED":
            raise HTTPException(status_code=400, detail=f"State Violation: APPROVED shifts to FULFILLED.")

        # Actuation & Payload Binding
        if payload.status == "APPROVED":
            cursor.execute(
                "UPDATE erp_procurement_queue SET status = ?, authorized_quantity = ? WHERE procurement_id = ?", 
                (payload.status, payload.authorized_quantity, procurement_id)
            )
        elif payload.status == "REJECTED":
            cursor.execute(
                "UPDATE erp_procurement_queue SET status = ? WHERE procurement_id = ?", 
                (payload.status, procurement_id)
            )
        
        # Autonomous Inventory Hook (FULFILLED only)
        if payload.status == "FULFILLED":
            if not db_authorized_qty:
                raise HTTPException(status_code=500, detail="Fatal execution error: FULFILLED triggered without prior authorized_quantity.")
            
            # Phase 1: Increment Master SKU Ledger
            cursor.execute(
                "UPDATE erp_skus SET quantity_on_hand = quantity_on_hand + ? WHERE sku_id = ?",
                (db_authorized_qty, sku_id)
            )

            # Phase 2: Instantiate Serialized Assets
            # Discrete insertion required for physical asset tracking
            for _ in range(db_authorized_qty):
                cursor.execute(
                    "INSERT INTO erp_parts (part_id, sku_id, status) VALUES (lower(hex(randomblob(16))), ?, 'IN_STOCK')",
                    (sku_id,)
                )

            # Phase 3: Mutate Procurement State
            cursor.execute(
                "UPDATE erp_procurement_queue SET status = 'FULFILLED' WHERE procurement_id = ?",
                (procurement_id,)
            )
            
        conn.commit()
        return {"detail": f"Procurement {procurement_id} mathematically fulfilled. Ledger synchronized."}
        
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Procurement Actuation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# [PHASE 40] Technician Execution Matrix
@api_router.patch("/mwo/{mwo_id}/execute")
def execute_mwo(
    mwo_id: str,
    payload: MWOExecutePayload,
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    tech_id = jwt_payload.get("sub")
    
    if role not in ["TECHNICIAN", "TECH", "ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Clearance required to execute work orders.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        if payload.action == "START":
            if role in ["ADMINISTRATOR", "ADMIN"]:
                cursor.execute(
                    "UPDATE work_orders SET status = 'IN_PROGRESS', execution_start = ? WHERE mwo_id = ? AND status IN ('ASSIGNED', 'UNASSIGNED', 'PAUSED')",
                    (time.time(), mwo_id)
                )
            else:
                cursor.execute(
                    "UPDATE work_orders SET status = 'IN_PROGRESS', execution_start = ? WHERE mwo_id = ? AND status IN ('ASSIGNED', 'PAUSED') AND assigned_tech = ?",
                    (time.time(), mwo_id, tech_id)
                )

            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="State Conflict: Work order is either already locked, not assigned to you, or invalid state.")
            
            conn.commit()
            return {"status": "success", "message": f"Execution Lock Acquired on {mwo_id}."}

        elif payload.action == "COMPLETE":
            cursor.execute("SELECT execution_start, accumulated_labor_seconds FROM work_orders WHERE mwo_id = ?", (mwo_id,))
            row = cursor.fetchone()
            if not row or not row["execution_start"]:
                raise HTTPException(status_code=400, detail="Cannot complete a work order that hasn't started.")
            
            end_time = time.time()
            start_time = row["execution_start"]
            accumulated = row["accumulated_labor_seconds"] or 0.0
            
            total_labor_seconds = accumulated + (end_time - start_time)
            labor_hours = total_labor_seconds / 3600.0

            if role in ["ADMINISTRATOR", "ADMIN"]:
                cursor.execute(
                    "UPDATE work_orders SET status = 'PENDING_REVIEW', execution_end = ?, labor_hours = ?, manual_log = ? WHERE mwo_id = ? AND status = 'IN_PROGRESS'",
                    (end_time, labor_hours, payload.manual_log, mwo_id)
                )
            else:
                cursor.execute(
                    "UPDATE work_orders SET status = 'PENDING_REVIEW', execution_end = ?, labor_hours = ?, manual_log = ? WHERE mwo_id = ? AND status = 'IN_PROGRESS' AND assigned_tech = ?",
                    (end_time, labor_hours, payload.manual_log, mwo_id, tech_id)
                )

            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="State Conflict: Cannot complete. Verification failed.")
            
            conn.commit()
            return {"status": "success", "message": f"Execution completed for {mwo_id}.", "labor_hours": round(labor_hours, 4)}

        elif payload.action == "PAUSE":
            # Calculate elapsed time and add to accumulated_labor_seconds
            cursor.execute("SELECT execution_start, accumulated_labor_seconds FROM work_orders WHERE mwo_id = ?", (mwo_id,))
            row = cursor.fetchone()
            if not row or not row["execution_start"]:
                raise HTTPException(status_code=400, detail="Cannot pause a work order that hasn't started.")
                
            elapsed = time.time() - row["execution_start"]
            new_accumulated = (row["accumulated_labor_seconds"] or 0.0) + elapsed
            
            cursor.execute(
                "UPDATE work_orders SET status = 'PAUSED', execution_start = NULL, accumulated_labor_seconds = ? WHERE mwo_id = ? AND status = 'IN_PROGRESS' AND (assigned_tech = ? OR ? IN ('ADMINISTRATOR', 'ADMIN'))",
                (new_accumulated, mwo_id, tech_id, role)
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="State Conflict: Cannot pause.")
            
            conn.commit()
            return {"status": "success", "message": f"Execution paused on {mwo_id}."}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Execution Route Error: {e}")
        raise HTTPException(status_code=500, detail="Internal execution error.")
    finally:
        conn.close()

@api_router.get("/system/directive")
def get_system_directive():
    """Exposes the Orchestration Boundary context to external agents."""
    if not GLOBAL_AI_DIRECTIVE_CONTEXT:
        raise HTTPException(status_code=503, detail="Directive context unavailable or not loaded.")
    return {"status": "success", "directive": GLOBAL_AI_DIRECTIVE_CONTEXT}

@api_router.get("/mwo/technicians")
def get_technicians(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Clearance required to view technician roster.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id as user_id, name FROM erp_employees WHERE role = 'TECH' AND is_active = 1")
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch technicians: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching technicians.")
    finally:
        conn.close()

@api_router.get("/mwo/hms")
def get_hms(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Clearance required to view HM roster.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id as user_id, name FROM erp_employees WHERE role = 'HM' AND is_active = 1")
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch hms: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching hms.")
    finally:
        conn.close()

@api_router.get("/mwo")
def get_mwo(limit: int = 50, offset: int = 0, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    user_id = jwt_payload.get("sub")
    
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cols = "w.mwo_id, w.status, w.dm_urgency, w.hm_priority, w.description, w.assigned_tech, w.assigned_hm_id, w.manual_log, w.created_at, w.triaged_at, w.execution_start, w.execution_end, w.completed_at, w.start_date, w.equipment_id, e.nomenclature as equipment_nomenclature, w.location_id, w.material_cost, w.archival_pdf_path, w.labor_hours"

        base_query = f"SELECT {cols} FROM work_orders w LEFT JOIN erp_equipment e ON w.equipment_id = e.equipment_id WHERE w.status IN ('UNASSIGNED', 'ASSIGNED', 'PENDING_REVIEW')"
        params = []
        
        if role == "HM":
            base_query += " AND w.assigned_hm_id = ?"
            params.append(user_id)
            
        base_query += " ORDER BY w.execution_start DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(base_query, tuple(params))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch work orders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching work orders.")
    finally:
        if conn:
            conn.close()



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

@api_router.get("/mwo/assigned")
def get_assigned_mwo(
    limit: int = Query(50), 
    offset: int = Query(0), 
    target_tech: str = Query(None),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    user_id = jwt_payload.get("sub")
    role = jwt_payload.get("role")
    
    # RBAC Impersonation Override
    if target_tech and role in ["ADMINISTRATOR", "ADMIN", "HM"]:
        user_id = target_tech
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cols = "w.mwo_id, w.status, w.dm_urgency, w.hm_priority, w.description, w.assigned_tech, w.consumed_sku, w.manual_log, w.created_at, w.triaged_at, w.execution_start, w.execution_end, w.completed_at, w.start_date, w.equipment_id, e.nomenclature as equipment_nomenclature, w.location_id, l.name as location_nomenclature, w.material_cost, w.archival_pdf_path"
        cursor.execute(
            f"SELECT {cols} FROM work_orders w LEFT JOIN erp_equipment e ON w.equipment_id = e.equipment_id LEFT JOIN erp_locations l ON w.location_id = l.id WHERE w.assigned_tech = ? AND w.status IN ('ASSIGNED', 'IN_PROGRESS', 'PAUSED', 'PENDING_REVIEW', 'COMPLETED') ORDER BY w.mwo_id DESC LIMIT ? OFFSET ?",
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
    resolution_notes: str = Field(..., min_length=1)
    labor_hours: float = Field(..., gt=0)

def archive_mwo_pdf_worker(mwo_id: str, resolution_notes: str, labor_hours: float):
    """
    [ASYNC ISOLATED WORKER]
    Target: CPU-Bound PDF Generation & I/O Archival
    Executes strictly off the primary FastAPI thread via BackgroundTasks.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        logger.info(f"[WORKER ENGAGED] Initiating asynchronous PDF archival for MWO: {mwo_id}")
        
        import time
        current_time = time.time()
        
        # 1. Explicit Data Extraction (Strict Enumeration)
        cursor.execute(
            """
            SELECT mwo_id, status, assigned_tech, equipment_id, description
            FROM work_orders 
            WHERE mwo_id = ?
            """, 
            (mwo_id,)
        )
        row = cursor.fetchone()
        if not row:
            logger.error(f"[WORKER FATAL] MWO {mwo_id} not found during archival extraction.")
            return
            
        mwo_data = dict(row)
        mwo_data["resolution_notes"] = resolution_notes
        mwo_data["labor_hours"] = labor_hours
        mwo_data["completed_at"] = current_time
        
        if not mwo_data:
            logger.error(f"[WORKER FATAL] MWO {mwo_id} not found during archival extraction.")
            return

        # 1b. Extract consumed parts from inventory ledger
        cursor.execute(
            """
            SELECT transaction_id, part_id, quantity_consumed, tech_id, transaction_timestamp
            FROM erp_inventory_ledger
            WHERE mwo_id = ?
            ORDER BY transaction_timestamp ASC
            """,
            (mwo_id,)
        )
        consumed_parts = [dict(row) for row in cursor.fetchall()]

        # 2. Native Python PDF Byte-Compilation (fpdf2 Spatial Doctrine)
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("helvetica", style="B", size=18)
        pdf.cell(0, 12, text="MAINTENANCE WORK ORDER ARCHIVE", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(4)
        pdf.set_font("helvetica", size=9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, text=f"Generated from sealed ledger transaction", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(8)

        # Separator
        pdf.set_draw_color(16, 185, 129)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

        # MWO Detail Rows
        detail_fields = [
            ("MWO ID", mwo_data["mwo_id"]),
            ("STATUS", mwo_data["status"]),
            ("ASSIGNED TECH", mwo_data["assigned_tech"] or "N/A"),
            ("EQUIPMENT ID", mwo_data["equipment_id"] or "N/A"),
            ("COMPLETED AT", mwo_data["completed_at"] or "N/A"),
            ("LABOR HOURS", str(mwo_data["labor_hours"] or "N/A")),
        ]

        for label, value in detail_fields:
            pdf.set_font("helvetica", style="B", size=10)
            pdf.cell(50, 8, text=f"{label}:", new_x="RIGHT", new_y="TOP")
            pdf.set_font("helvetica", size=10)
            pdf.cell(0, 8, text=str(value), new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)

        # Description
        if mwo_data["description"]:
            pdf.set_font("helvetica", style="B", size=10)
            pdf.cell(0, 8, text="DESCRIPTION:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", size=10)
            pdf.multi_cell(0, 6, text=str(mwo_data["description"]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # Resolution Notes
        pdf.set_font("helvetica", style="B", size=10)
        pdf.cell(0, 8, text="RESOLUTION NOTES:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", size=10)
        pdf.multi_cell(0, 6, text=str(mwo_data["resolution_notes"] or "N/A"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        # Consumed Parts Table
        if consumed_parts:
            pdf.set_draw_color(16, 185, 129)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(4)
            pdf.set_font("helvetica", style="B", size=11)
            pdf.cell(0, 8, text="CONSUMED PARTS LEDGER", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

            # Table header
            pdf.set_font("helvetica", style="B", size=9)
            pdf.cell(35, 7, text="TXN ID", new_x="RIGHT", new_y="TOP")
            pdf.cell(30, 7, text="PART ID", new_x="RIGHT", new_y="TOP")
            pdf.cell(15, 7, text="QTY", new_x="RIGHT", new_y="TOP")
            pdf.cell(30, 7, text="TECH", new_x="RIGHT", new_y="TOP")
            pdf.cell(0, 7, text="TIMESTAMP", new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("helvetica", size=9)
            for part in consumed_parts:
                pdf.cell(35, 6, text=str(part["transaction_id"]), new_x="RIGHT", new_y="TOP")
                pdf.cell(30, 6, text=str(part["part_id"]), new_x="RIGHT", new_y="TOP")
                pdf.cell(15, 6, text=str(part["quantity_consumed"]), new_x="RIGHT", new_y="TOP")
                pdf.cell(30, 6, text=str(part["tech_id"]), new_x="RIGHT", new_y="TOP")
                pdf.cell(0, 6, text=str(part["transaction_timestamp"] or ""), new_x="LMARGIN", new_y="NEXT")

        # 3. Defensive Physical I/O Archival
        directory_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "archives/work_orders"))
        os.makedirs(directory_path, exist_ok=True)
        
        file_path = f"{directory_path}/{mwo_id}.pdf"
        pdf.output(file_path)
        logger.info(f"[WORKER I/O] Byte-compilation physically written to {file_path}")

        # 4. State Mutation (Schema Linkage & Time Telemetry)
        cursor.execute(
            """
            UPDATE work_orders 
            SET archival_pdf_path = ?, status = 'COMPLETED', completed_at = ?, resolution_notes = ?, labor_hours = ? 
            WHERE mwo_id = ?
            """,
            (file_path, current_time, resolution_notes, labor_hours, mwo_id)
        )
        conn.commit()
        logger.info(f"[WORKER SUCCESS] Archival cycle finalized for MWO: {mwo_id}")

    except Exception as e:
        logger.error(f"[WORKER FATAL] PDF Archival failed for MWO {mwo_id}: {e}")
    finally:
        conn.close()

@api_router.get("/mwo/archive/list")
def get_archive_list(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    user_id = jwt_payload.get("sub")
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cols = "w.mwo_id, w.status, w.description, w.completed_at, w.equipment_id, e.nomenclature as equipment_nomenclature, w.archival_pdf_path"
        base_query = f"SELECT {cols} FROM work_orders w LEFT JOIN erp_equipment e ON w.equipment_id = e.equipment_id WHERE w.status = 'COMPLETED'"
        params = []
        
        if role == "DM":
            base_query += " AND e.department_id = (SELECT department_id FROM erp_employees WHERE id = ?)"
            params.append(user_id)
        elif role == "HM":
            base_query += " AND w.assigned_hm_id = ?"
            params.append(user_id)
        elif role == "TECH":
            base_query += " AND w.assigned_tech = ?"
            params.append(user_id)
        elif role not in ["ADMINISTRATOR", "ADMIN"]:
            raise HTTPException(status_code=403, detail="RBAC Violation: Invalid role clearance.")
            
        base_query += " ORDER BY w.completed_at DESC"
        
        cursor.execute(base_query, tuple(params))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch archive list: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching archive list.")
    finally:
        conn.close()

@api_router.get("/mwo/{mwo_id}/archive")
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
            if role == "DM":
                cursor.execute("SELECT department_id FROM erp_employees WHERE id = ?", (user_id,))
                dm_record = cursor.fetchone()
                if not dm_record:
                    raise HTTPException(status_code=403, detail="RBAC Violation: DM profile not found.")
                
                dm_dept = dm_record['department_id']
                cursor.execute(
                    "SELECT e.department_id FROM work_orders w JOIN erp_equipment e ON w.equipment_id = e.equipment_id WHERE w.mwo_id = ?",
                    (mwo_id,)
                )
                eq_record = cursor.fetchone()
                if not eq_record or eq_record['department_id'] != dm_dept:
                    raise HTTPException(status_code=403, detail="RBAC Violation: MWO does not belong to your department.")
            # Strict Tech Validation: Must be the exactly assigned operator
            elif role == "TECH" and record['assigned_tech'] != user_id:
                raise HTTPException(status_code=403, detail="RBAC Violation: You are not authorized to view this structural archive.")
            elif role not in ["TECH", "DM"]:
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

@api_router.post("/mwo/{mwo_id}/complete", status_code=202)
def complete_mwo(
    mwo_id: str, 
    payload: TechCompletePayload, 
    background_tasks: BackgroundTasks, 
    jwt_payload: dict = Depends(verify_jwt_token)
):
    tech_id = jwt_payload.get("sub")
    role = jwt_payload.get("role")
    
    if role not in ["ADMINISTRATOR", "ADMIN", "HM", "TECH"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Clearance required to finalize MWO.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        
        # 1. RBAC Parity Check + State Validation
        cursor.execute("SELECT status, assigned_tech FROM work_orders WHERE mwo_id = ?", (mwo_id,))
        mwo_record = cursor.fetchone()
        if not mwo_record:
            raise HTTPException(status_code=404, detail="MWO not found.")
        if mwo_record['status'] == 'COMPLETED':
            raise HTTPException(status_code=400, detail="MWO is already finalized.")
        if mwo_record['status'] not in ['IN_PROGRESS', 'PENDING_REVIEW']:
            raise HTTPException(status_code=400, detail=f"State Violation: MWO must be IN_PROGRESS or PENDING_REVIEW to finalize. Current: {mwo_record['status']}")

        # RBAC Enforcement: TECH-tier must be the assigned operator
        if role in ["TECH"] and mwo_record['assigned_tech'] != tech_id:
            raise HTTPException(status_code=403, detail="RBAC Violation: Technician is not the assigned operator for this MWO.")

        # 2. Asynchronous Dispatch: PDF generation & DB completion in background worker
        background_tasks.add_task(archive_mwo_pdf_worker, mwo_id, payload.resolution_notes, payload.labor_hours)
        
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=202, content={
            "status": "success", 
            "message": f"MWO {mwo_id} accepted. PDF archival and finalization dispatched asynchronously."
        })
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"MWO Completion Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during MWO termination.")
    finally:
        conn.close()

@api_router.patch("/mwo/{mwo_id}")
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
                update_data["start_date"] = current_time

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
            cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path, labor_hours"
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
        cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path, labor_hours"
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

@api_router.post("/mwo/broadcast")
async def broadcast_mwo_state():
    await sync_memory_bus()
    return {"status": "success", "message": "Broadcast written to shared memory."}

@api_router.post("/orders/submit")
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

@api_router.post("/orders/assign")
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
    description: str
    equipment_id: str
    location_id: str
    urgency: str
    assigned_tech: Optional[str] = None
    status: Optional[str] = "PENDING_REVIEW"
    impersonated_creator_id: Optional[str] = None

    @field_validator('equipment_id', 'location_id')
    @classmethod
    def reject_concatenated_strings(cls, v: str) -> str:
        if '(' in v or 'Loc:' in v or ')' in v or ' ' in v:
            raise ValueError("Foreign Keys must be absolute IDs, not concatenated display strings.")
        return v

@api_router.post("/mwo")
async def create_mwo(payload: NewMWO, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    creator_id = jwt_payload.get("sub")
    
    if role not in ["ADMINISTRATOR", "ADMIN", "DM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Unauthorized identity.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        final_creator_id = creator_id
        if payload.impersonated_creator_id and role == "DM":
            # Security check: Verify the impersonated user is in the DM's department
            cursor.execute("SELECT department_id FROM erp_employees WHERE id = ?", (creator_id,))
            dm_dept_row = cursor.fetchone()
            cursor.execute("SELECT department_id FROM erp_employees WHERE id = ?", (payload.impersonated_creator_id,))
            impersonated_dept_row = cursor.fetchone()

            if not dm_dept_row or not impersonated_dept_row or dm_dept_row['department_id'] != impersonated_dept_row['department_id']:
                raise HTTPException(status_code=403, detail="RBAC Violation: Cannot impersonate users outside your department.")
            
            final_creator_id = payload.impersonated_creator_id

        current_time = time.time()
        
        # Auto-generate ID autonomously without client input
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

        cursor.execute("SELECT assigned_hm_id FROM erp_equipment WHERE equipment_id = ?", (payload.equipment_id,))
        eq_row = cursor.fetchone()
        assigned_hm_id = eq_row['assigned_hm_id'] if eq_row else None

        cursor.execute(
            """
            INSERT INTO work_orders 
            (mwo_id, description, equipment_id, location_id, dm_urgency, assigned_tech, assigned_hm_id, status, hm_priority, execution_start, created_by) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (final_mwo_id, payload.description, payload.equipment_id, payload.location_id, payload.urgency, payload.assigned_tech, assigned_hm_id, "UNASSIGNED", "Normal", current_time, final_creator_id)
        )
        conn.commit()
        
        # Fetch the newly created record
        cols = "mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at, start_date, equipment_id, location_id, material_cost, archival_pdf_path"
        cursor.execute(f"SELECT {cols} FROM work_orders WHERE mwo_id = ?", (final_mwo_id,))
        new_row = cursor.fetchone()
        
        return {"status": "success", "message": "MWO created successfully", "data": dict(new_row) if new_row else {}}
    except HTTPException:
        raise
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

@api_router.post("/admin/employees/bulk-upload", status_code=202)
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

@api_router.post("/admin/mwo/bulk-upload", status_code=202)
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

@api_router.post("/admin/users/bulk-upload", status_code=202)
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

@api_router.get("/orders/active")
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


@api_router.get("/admin/users")
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
            
@api_router.get("/admin/users/{user_id}/audit-log")
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

@api_router.delete("/admin/users/{user_id}", status_code=204)
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

@api_router.put("/admin/users/{user_id}/escalate")
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

# [PHASE 36.1] MWO Queue & Assignment Dispatch

@api_router.get("/work-orders/queue")
def get_work_orders_queue(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    target_dm: Optional[str] = Query(None),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        role = jwt_payload.get("role")
        user_id = jwt_payload.get("sub")
        
        active_user = target_dm if target_dm and role in ["ADMINISTRATOR", "ADMIN"] else user_id
        active_role = "DM" if target_dm and role in ["ADMINISTRATOR", "ADMIN"] else role
        
        query = "SELECT COUNT(*) as total_count FROM work_orders w"
        data_query = "SELECT w.mwo_id, w.status, w.dm_urgency, w.hm_priority, w.equipment_id, w.description, w.created_at FROM work_orders w"
        params = []
        
        if active_role == "DM":
            query += " JOIN erp_equipment e ON w.equipment_id = e.equipment_id WHERE e.department_id = (SELECT department_id FROM erp_employees WHERE id = ?)"
            data_query += " JOIN erp_equipment e ON w.equipment_id = e.equipment_id WHERE e.department_id = (SELECT department_id FROM erp_employees WHERE id = ?)"
            params.append(active_user)
        else:
            query += " WHERE 1=1"
            data_query += " WHERE 1=1"
        
        if status:
            query += " AND w.status = ?"
            data_query += " AND w.status = ?"
            params.append(status)
            
        cursor.execute(query, params)
        count_row = cursor.fetchone()
        total_count = count_row['total_count'] if count_row else 0
        
        data_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(data_query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "total_count": total_count, "data": rows}
    except Exception as e:
        logger.error(f"Failed to fetch MWO queue: {e}")
        raise HTTPException(status_code=500, detail="Queue synchronization failed.")
    finally:
        conn.close()

class AssignMWOPayload(BaseModel):
    assigned_tech_id: str
    hm_priority: str = "Normal"

@api_router.patch("/mwo/{mwo_id}/assign")
def assign_mwo(
    mwo_id: str,
    payload: AssignMWOPayload,
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    user_id = jwt_payload.get("sub")
    
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        
        cursor.execute("SELECT is_active, department_id FROM erp_employees WHERE id = ? AND role = 'TECH'", (payload.assigned_tech_id,))
        tech_emp = cursor.fetchone()
        
        if not tech_emp:
            raise HTTPException(status_code=404, detail="Technician not found or invalid role.")
            
        if not tech_emp['is_active']:
            raise HTTPException(status_code=400, detail="Structural Violation: Cannot assign to an inactive technician.")
            
        if role == "HM":
            cursor.execute("SELECT department_id FROM erp_employees WHERE id = ?", (user_id,))
            hm_emp = cursor.fetchone()
            if hm_emp and hm_emp['department_id'] != tech_emp['department_id']:
                raise HTTPException(status_code=403, detail="RBAC Violation: Cannot assign a technician outside your departmental isolation boundary.")
            
        triaged_time = time.time()
        
        cursor.execute(
            """
            UPDATE work_orders 
            SET assigned_tech = ?, hm_priority = ?, triaged_at = ?, status = 'ASSIGNED' 
            WHERE mwo_id = ? AND status IN ('UNASSIGNED', 'UNASSIGNED_ESCALATION')
            """,
            (payload.assigned_tech_id, payload.hm_priority, triaged_time, mwo_id)
        )
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="MWO not found or already assigned.")
            
        conn.commit()
        return {"status": "success", "message": f"MWO {mwo_id} successfully assigned to {payload.assigned_tech_id}."}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Assignment Actuation Error: {e}")
        raise HTTPException(status_code=500, detail="Assignment failed.")
    finally:
        conn.close()

@api_router.get("/employees")
def get_employees(
    role: Optional[str] = Query(None),
    is_active: Optional[int] = Query(None),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT id, name, role, is_active FROM erp_employees WHERE 1=1"
        params = []
        if role:
            query += " AND role = ?"
            params.append(role)
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(is_active)
            
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "data": rows}
    finally:
        conn.close()

# Personnel Bulk
@api_router.get("/admin/ingest/personnel/template")
def get_personnel_ingestion_template(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM erp_departments")
        departments = [row['name'] for row in c.fetchall()]
        c.execute("SELECT name FROM erp_employees WHERE role='HM'")
        hms = [row['name'] for row in c.fetchall()]
    finally:
        conn.close()
        
    headers = ["name", "role", "pin_code", "department_name", "reports_to_hm_name"]
    return generate_xlsx_template(headers, "personnel_ingestion_template", departments=departments, hms=hms)

@api_router.post("/admin/ingest/personnel/bulk")
async def bulk_ingest_personnel(file: UploadFile = File(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
        
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Invalid file format.")
        
    content = await file.read()
    try:
        wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
        ws = wb.active
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        rows = []
        for row_values in ws.iter_rows(min_row=2, values_only=True):
            if not any(row_values): continue
            row_dict = dict(zip(header_row, row_values))
            rows.append(row_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read XLSX: {e}")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        cursor.execute("SELECT id, name FROM erp_departments")
        dep_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT id, name FROM erp_employees WHERE role = 'HM'")
        hm_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}

        cursor.execute("BEGIN TRANSACTION")
        
        import bcrypt
        
        # Pass 1: Parse and validate all users, assign IDs, and update hm_map
        parsed_users = []
        for i, row in enumerate(rows):
            row_data = {k.strip(): str(v).strip() if v is not None else None for k, v in row.items()}
            
            name = row_data.get('name')
            prole = row_data.get('role', '').upper()
            pin = row_data.get('pin_code')
            if not name or not prole or not pin:
                raise ValueError(f"Row {i+2}: Missing required fields.")
                
            dep_name = row_data.get('department_name')
            if not dep_name:
                raise ValueError(f"Row {i+2}: Missing department_name")
            if dep_name.lower() not in dep_map:
                new_dep = f"DEP-{uuid.uuid4().hex[:6].upper()}"
                cursor.execute("INSERT INTO erp_departments (id, name) VALUES (?, ?)", (new_dep, dep_name.strip()))
                dep_map[dep_name.lower()] = new_dep
            dep_id = dep_map[dep_name.lower()]
            
            new_id = f"U-{uuid.uuid4().hex[:6].upper()}"
            
            if prole in ['HM', 'DM', 'ADMINISTRATOR', 'ADMIN']:
                hm_map[name.lower().strip()] = new_id
                
            parsed_users.append({
                'row_index': i + 2,
                'id': new_id,
                'name': name,
                'role': prole,
                'pin': pin,
                'department_id': dep_id,
                'reports_to': row_data.get('reports_to_hm_name')
            })

        # Sort so that Managers are inserted before Technicians to satisfy Foreign Key constraints
        parsed_users.sort(key=lambda u: 0 if u['role'] in ['ADMINISTRATOR', 'ADMIN', 'DM', 'HM'] else 1)

        # Pass 2: Resolve HM relationships and insert
        inserted_count = 0
        for user in parsed_users:
            hm_name = user['reports_to']
            hm_id = None
            if hm_name:
                if hm_name.lower().strip() not in hm_map:
                    raise ValueError(f"Row {user['row_index']}: Unknown HM Name '{hm_name}'")
                hm_id = hm_map[hm_name.lower().strip()]
                
            if user['role'] in ['TECH', 'TECHNICIAN'] and not hm_id:
                raise ValueError(f"Row {user['row_index']}: TECH must have a reports_to_hm_name")

            pin_hash = bcrypt.hashpw(user['pin'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            cursor.execute(
                "INSERT INTO erp_employees (id, name, role, pin_hash, is_active, department_id, reports_to_hm_id) VALUES (?, ?, ?, ?, 1, ?, ?)",
                (user['id'], user['name'], user['role'], pin_hash, user['department_id'], hm_id)
            )
            inserted_count += 1
            
        conn.commit()
        return {"status": "success", "message": f"Successfully ingested {inserted_count} personnel."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# Parts Bulk
@api_router.get("/admin/ingest/part/template")
def get_part_ingestion_template(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM erp_categories")
        categories = [row['name'] for row in c.fetchall()]
    finally:
        conn.close()
        
    headers = ["nomenclature", "category_name", "quantity_on_hand", "reorder_threshold", "unit_cost"]
    return generate_xlsx_template(headers, "part_ingestion_template", categories=categories)

@api_router.post("/admin/ingest/part/bulk")
async def bulk_ingest_part(file: UploadFile = File(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
        
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Invalid file format.")
        
    content = await file.read()
    try:
        wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
        ws = wb.active
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        rows = []
        for row_values in ws.iter_rows(min_row=2, values_only=True):
            if not any(row_values): continue
            row_dict = dict(zip(header_row, row_values))
            rows.append(row_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read XLSX: {e}")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        cursor.execute("SELECT id, name FROM erp_categories")
        cat_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}

        cursor.execute("BEGIN TRANSACTION")
        
        inserted_count = 0
        for i, row in enumerate(rows):
            row_data = {k.strip(): str(v).strip() if v is not None else None for k, v in row.items()}
            
            cat_name = row_data.get('category_name')
            if not cat_name:
                raise ValueError(f"Row {i+2}: Missing category_name")
            if cat_name.lower() not in cat_map:
                new_cat = f"CAT-{uuid.uuid4().hex[:6].upper()}"
                cursor.execute("INSERT INTO erp_categories (id, name) VALUES (?, ?)", (new_cat, cat_name.strip()))
                cat_map[cat_name.lower()] = new_cat
            cat_id = cat_map[cat_name.lower()]

            new_id = f"PRT-{uuid.uuid4().hex[:6].upper()}"
            
            cursor.execute(
                "INSERT INTO erp_parts (part_id, nomenclature, category_id, quantity_on_hand, reorder_threshold, unit_cost) VALUES (?, ?, ?, ?, ?, ?)",
                (new_id, row_data.get('nomenclature'), cat_id, int(row_data.get('quantity_on_hand', 0)), int(row_data.get('reorder_threshold', 5)), float(row_data.get('unit_cost', 0.0)))
            )
            inserted_count += 1
            
        conn.commit()
        return {"status": "success", "message": f"Successfully ingested {inserted_count} parts."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- PHASE 44 SKU INGESTION & LEDGER ---
@api_router.post("/inventory/skus", status_code=201)
def ingest_sku(payload: SKUCreate, jwt_payload: dict = Depends(verify_jwt_token)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Ensure the matrix exists or gracefully fail
        cursor.execute(
            """
            INSERT INTO erp_skus (sku_id, nomenclature, unit_cost, reorder_threshold, quantity_on_hand)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.sku_id, payload.nomenclature, payload.unit_cost, payload.reorder_threshold, 0)
        )
        conn.commit()
        return {"status": "success", "message": f"SKU {payload.sku_id} ingested."}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="SKU already exists.")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database insertion failed: {e}")
    finally:
        conn.close()

@api_router.get("/inventory/skus")
def get_skus(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM erp_skus")
        total_row = cursor.fetchone()
        total = total_row["count"] if total_row else 0
        
        cursor.execute("SELECT sku_id, nomenclature, unit_cost, reorder_threshold, quantity_on_hand FROM erp_skus LIMIT ? OFFSET ?", (limit, offset))
        rows = [dict(row) for row in cursor.fetchall()]
        return {
            "items": rows,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"SKU Ledger fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Matrix synchronization failed.")
    finally:
        conn.close()

@api_router.post("/inventory/parts", status_code=201)
def ingest_part(payload: PartCreate, token_payload: dict = Depends(verify_jwt_token)):
    part_id = f"PRT-{uuid.uuid4().hex[:8].upper()}"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION;")
        
        cursor.execute(
            "INSERT INTO erp_parts (part_id, sku_id, serial_number) VALUES (?, ?, ?)",
            (part_id, payload.sku_id, payload.serial_number)
        )
        
        cursor.execute(
            "UPDATE erp_skus SET quantity_on_hand = quantity_on_hand + 1 WHERE sku_id = ?",
            (payload.sku_id,)
        )
        
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        error_msg = str(e).lower()
        if "foreign key" in error_msg:
            raise HTTPException(status_code=400, detail=f"Invalid SKU ID: {payload.sku_id} does not exist in the financial catalog.")
        if "unique" in error_msg:
            raise HTTPException(status_code=409, detail="Serial number already exists in the matrix.")
        raise HTTPException(status_code=500, detail="Database integrity violation.")
    finally:
        conn.close()

    return {"status": "success", "message": f"Part {part_id} physically instantiated."}

@api_router.get("/inventory/parts")
def get_paginated_parts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    token_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM erp_parts")
        total_row = cursor.fetchone()
        total = total_row["count"] if total_row else 0
        
        cursor.execute("""
            SELECT p.part_id, p.sku_id, s.nomenclature, p.serial_number, p.status 
            FROM erp_parts p
            JOIN erp_skus s ON p.sku_id = s.sku_id
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = [dict(row) for row in cursor.fetchall()]
        return {
            "items": rows,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Part matrix extraction failed: {e}")
        raise HTTPException(status_code=500, detail="Matrix extraction failed.")
    finally:
        conn.close()

@api_router.post("/inventory/mutate")
def mutate_inventory(payload: InventoryMutation, jwt_payload: dict = Depends(verify_jwt_token)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        cursor.execute("SELECT quantity_on_hand FROM erp_skus WHERE sku_id = ?", (payload.sku_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="SKU not found.")
            
        current_qty = row["quantity_on_hand"]
        if payload.mutation_type == "IN":
            new_qty = current_qty + payload.quantity
        else:
            if current_qty < payload.quantity:
                raise HTTPException(status_code=400, detail="Insufficient quantity_on_hand for OUT mutation.")
            new_qty = current_qty - payload.quantity
            
        cursor.execute("UPDATE erp_skus SET quantity_on_hand = ? WHERE sku_id = ?", (new_qty, payload.sku_id))
        conn.commit()
        return {"status": "success", "quantity_on_hand": new_qty}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Mutation error: {e}")
        raise HTTPException(status_code=500, detail="Internal Execution Error.")
    finally:
        conn.close()

@api_router.get("/users")
def get_paginated_users(
    limit: int = Query(50, ge=1, le=100, description="Strict pagination limit"),
    offset: int = Query(0, ge=0, description="Strict pagination offset"),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Execute COUNT() for envelope
        cursor.execute("SELECT COUNT(*) FROM erp_employees")
        total = cursor.fetchone()[0]
        
        # 2. Execute LIMIT/OFFSET extraction
        cursor.execute(
            """
            SELECT id as user_id, name, role, department_id as department, reports_to_hm_id
            FROM erp_employees
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        
        # 3. Return explicit pagination envelope
        return {
            "items": rows,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")
        raise HTTPException(status_code=500, detail="Matrix synchronization failed.")
    finally:
        conn.close()

@api_router.post("/work-orders/{mwo_id}/consume", status_code=201)
def ingest_mwo_consumption(
    mwo_id: str,
    payload: MwoConsumptionPayload,
    token_payload: dict = Depends(verify_jwt_token)
):
    tech_id = token_payload.get("sub")
    if not tech_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Identity Gateway missing sub claim")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # 2. Enforce Strict Write-Lock to prevent SQLITE_BUSY deadlocks
        cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
        
        # 3. Assert MWO Execution State
        cursor.execute("SELECT status FROM work_orders WHERE mwo_id = ?", (mwo_id,))
        mwo = cursor.fetchone()
        if not mwo or mwo["status"] not in ('ASSIGNED', 'IN_PROGRESS', 'DISPATCHED'):
            raise HTTPException(status_code=400, detail="Invalid or inactive MWO target.")

        import time
        import uuid
        
        # 4. Iterate and Execute Discrete Physical Math
        consumed_ledgers = []
        for part_id in payload.part_ids:
            cursor.execute("SELECT sku_id, status FROM erp_parts WHERE part_id = ?", (part_id,))
            part = cursor.fetchone()
            
            if not part or part["status"] != "IN_STOCK":
                raise HTTPException(status_code=400, detail=f"Part {part_id} is invalid or already consumed.")
                
            consumption_id = f"CNS-{uuid.uuid4().hex[:8].upper()}"
            
            # A. Log Junction Consumption (Strictly QTY 1 for discrete assets)
            cursor.execute(
                """
                INSERT INTO mwo_consumed_parts 
                (consumption_id, mwo_id, part_id, quantity_consumed, consumed_at, logged_by_tech_id) 
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (consumption_id, mwo_id, part_id, 1, time.time(), tech_id)
            )
            
            # B. Mutate Physical Asset Status
            cursor.execute("UPDATE erp_parts SET status = 'CONSUMED' WHERE part_id = ?", (part_id,))
            
            # C. Deduct Exactly 1 from the SKU Ledger
            cursor.execute(
                "UPDATE erp_skus SET quantity_on_hand = quantity_on_hand - 1 WHERE sku_id = ?",
                (part["sku_id"],)
            )
            consumed_ledgers.append(part_id)

        conn.commit()
        return {
            "status": "success",
            "message": f"{len(consumed_ledgers)} discrete parts mathematically consumed against MWO {mwo_id}."
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"Consumption Execution Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@api_router.get("/admin/procurement", response_model=Dict[str, Any])
def get_procurement_ledger(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Clearance required to view procurement ledger.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Phase 1: Total Count Extraction
        cursor.execute("SELECT COUNT(procurement_id) FROM erp_procurement_queue")
        total_records = cursor.fetchone()[0]

        # Phase 2: Explicit Column Pagination Extraction
        query = """
            SELECT 
                p.procurement_id,
                p.part_id,
                s.nomenclature,
                s.quantity_on_hand,
                s.reorder_threshold,
                s.unit_cost,
                p.status,
                p.triggered_at
            FROM 
                erp_procurement_queue p
            JOIN 
                erp_skus s ON p.part_id = s.sku_id
            ORDER BY 
                p.triggered_at DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, (limit, offset))
        rows = [dict(row) for row in cursor.fetchall()]

        # Return strict Unified I/O Serialization Envelope
        return {
            "items": rows,
            "total": total_records,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database execution anomaly: {str(e)}")
    finally:
        conn.close()


# ==========================================
# PHASE 48: MASTER DATA HYDRATION ROUTES
# ==========================================
# Pydantic Models for deterministic Master Data ingestion.
# All models accept an optional client-side `id` to support
# scripted hydration with deterministic primary keys.

class LocationCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=2, description="Physical location name")

class DepartmentCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=2, description="Operational department name")

class CategoryCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=2, description="Equipment/SKU category name")

class Phase48EmployeeCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=2)
    role: str = Field(..., description="ADMINISTRATOR, ADMIN, HM, TECH")
    pin_code: str = Field(..., min_length=4)
    department_id: str = Field(..., description="FK to erp_departments.id")
    reports_to_hm_id: Optional[str] = None

class Phase48SkuCreate(BaseModel):
    id: Optional[str] = None
    nomenclature: str = Field(..., min_length=2)
    category_id: str = Field(..., description="FK to erp_categories.id")
    unit_cost: float = Field(..., ge=0.0)
    reorder_threshold: int = Field(..., ge=0)

class Phase48EquipmentCreate(BaseModel):
    id: Optional[str] = None
    nomenclature: str = Field(..., min_length=2)
    category_id: str = Field(..., description="FK to erp_categories.id")
    department_id: str = Field(..., description="FK to erp_departments.id")
    location_id: str = Field(..., description="FK to erp_locations.id")
    assigned_hm_id: str = Field(..., description="FK to erp_employees.id")
    status: str = Field(default="ACTIVE")


# --- LEVEL 0 ROUTES ---

@api_router.post("/locations", status_code=201)
def hydrate_location(payload: LocationCreate, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        loc_id = payload.id if payload.id else f"LOC-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("INSERT INTO erp_locations (id, name) VALUES (?, ?)", (loc_id, payload.name))
        conn.commit()
        return {"detail": "Record successfully ingested."}
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"Location IntegrityError: {e}")
        raise HTTPException(status_code=400, detail=f"Structural Violation: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Location Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Execution Error: {e}")
    finally:
        conn.close()

@api_router.post("/departments", status_code=201)
def hydrate_department(payload: DepartmentCreate, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        dep_id = payload.id if payload.id else f"DEP-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("INSERT INTO erp_departments (id, name) VALUES (?, ?)", (dep_id, payload.name))
        conn.commit()
        return {"detail": "Record successfully ingested."}
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"Department IntegrityError: {e}")
        raise HTTPException(status_code=400, detail=f"Structural Violation: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Department Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Execution Error: {e}")
    finally:
        conn.close()

@api_router.post("/categories", status_code=201)
def hydrate_category(payload: CategoryCreate, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        cat_id = payload.id if payload.id else f"CAT-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("INSERT INTO erp_categories (id, name) VALUES (?, ?)", (cat_id, payload.name))
        conn.commit()
        return {"detail": "Record successfully ingested."}
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"Category IntegrityError: {e}")
        raise HTTPException(status_code=400, detail=f"Structural Violation: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Category Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Execution Error: {e}")
    finally:
        conn.close()


# --- LEVEL 1 ROUTES ---

@api_router.post("/employees", status_code=201)
def hydrate_employee(payload: Phase48EmployeeCreate, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
    conn = get_db_connection()
    try:
        import bcrypt
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        emp_id = payload.id if payload.id else f"U-{uuid.uuid4().hex[:6].upper()}"
        pin_hash = bcrypt.hashpw(payload.pin_code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute(
            "INSERT INTO erp_employees (id, name, role, pin_hash, is_active, department_id, reports_to_hm_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (emp_id, payload.name, payload.role, pin_hash, 1, payload.department_id, payload.reports_to_hm_id)
        )
        conn.commit()
        return {"detail": "Record successfully ingested."}
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"Employee IntegrityError: {e}")
        raise HTTPException(status_code=400, detail=f"Structural Violation: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Employee Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Execution Error: {e}")
    finally:
        conn.close()

@api_router.post("/skus", status_code=201)
def hydrate_sku(payload: Phase48SkuCreate, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        sku_id = payload.id if payload.id else f"SKU-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute(
            "INSERT INTO erp_skus (sku_id, nomenclature, unit_cost, reorder_threshold, quantity_on_hand) VALUES (?, ?, ?, ?, ?)",
            (sku_id, payload.nomenclature, payload.unit_cost, payload.reorder_threshold, 0)
        )
        conn.commit()
        return {"detail": "Record successfully ingested."}
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"SKU IntegrityError: {e}")
        raise HTTPException(status_code=400, detail=f"Structural Violation: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"SKU Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Execution Error: {e}")
    finally:
        conn.close()


# --- LEVEL 2 ROUTES ---

@api_router.post("/equipment", status_code=201)
def hydrate_equipment(payload: Phase48EquipmentCreate, jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        eq_id = payload.id if payload.id else f"EQ-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute(
            "INSERT INTO erp_equipment (equipment_id, nomenclature, category_id, status, department_id, location_id, assigned_hm_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (eq_id, payload.nomenclature, payload.category_id, payload.status, payload.department_id, payload.location_id, payload.assigned_hm_id)
        )
        conn.commit()
        return {"detail": "Record successfully ingested."}
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"Equipment IntegrityError: {e}")
        raise HTTPException(status_code=400, detail=f"Structural Violation: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Equipment Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Execution Error: {e}")
    finally:
        conn.close()

@api_router.get("/dm/personnel")
def get_department_personnel(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    user_id = jwt_payload.get("sub")

    if role not in ["DM", "ADMIN", "ADMINISTRATOR"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: DM clearance required.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # First, get the DM's department ID
        cursor.execute("SELECT department_id FROM erp_employees WHERE id = ?", (user_id,))
        user_record = cursor.fetchone()
        
        if not user_record:
            raise HTTPException(status_code=404, detail="DM record not found.")
        
        department_id = user_record['department_id']
        
        # Then, get all employees in that department
        cursor.execute("SELECT id, name, role FROM erp_employees WHERE department_id = ? AND is_active = 1", (department_id,))
        personnel = [dict(row) for row in cursor.fetchall()]
        
        return {"status": "success", "data": personnel}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch department personnel: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")
    finally:
        conn.close()

app.include_router(api_router)

# --- FRONTEND DEPLOYMENT ---
frontend_dist_path = os.path.join(_erp, 'maintenance_frontend', 'dist')

if os.path.exists(frontend_dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
