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
env_path = os.path.join(_factory, '.env')
load_dotenv(env_path)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MaintenanceBackend")
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

class PinVerify(BaseModel):
    pin: str

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
        cursor.execute("SELECT * FROM work_orders WHERE mwo_id = ?", (mwo_id,))
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

@app.post("/api/user/authenticate")
def authenticate_user(payload: PinVerify, response: Response):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT e.id, e.name, e.authorization_level
            FROM erp_employees e
            WHERE e.pin_code = ?
        """
        cursor.execute(query, (payload.pin,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="Authorization Denied.")
            
        role = row["authorization_level"].upper()
            
        if role not in ["ADMIN", "ADMINISTRATOR", "DM", "HM", "TECHNICIAN", "TECH"]:
            raise HTTPException(status_code=500, detail="Invalid DB Role Mapping.")
        
        access_token = create_access_token(user_id=row["id"], role=role)
        refresh_token = create_refresh_token(user_id=row["id"], role=role)
        
        response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="Strict")
        
        return {
            "status": "success",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": row["id"],
                "name": row["name"],
                "role": role
            }
        }
    finally:
        if conn:
            conn.close()

@app.get("/api/system/directive")
def get_system_directive():
    """Exposes the Orchestration Boundary context to external agents."""
    if not GLOBAL_AI_DIRECTIVE_CONTEXT:
        raise HTTPException(status_code=503, detail="Directive context unavailable or not loaded.")
    return {"status": "success", "directive": GLOBAL_AI_DIRECTIVE_CONTEXT}

@app.get("/api/mwo")
def get_mwo():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM work_orders")
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
            cursor.execute("SELECT * FROM work_orders WHERE mwo_id = ?", (mwo_id,))
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
        cursor.execute("SELECT * FROM work_orders WHERE status != 'COMPLETED' COLLATE NOCASE")
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
    assigned_tech: str
    status: str = "PENDING_REVIEW"

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
            (mwo_id, description, assigned_tech, status, hm_priority, dm_urgency, execution_start) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (final_mwo_id, payload.description, payload.assigned_tech, payload.status, "Normal", "Normal", current_time)
        )
        conn.commit()
        
        # Fetch the newly created record
        cursor.execute("SELECT * FROM work_orders WHERE mwo_id = ?", (final_mwo_id,))
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
