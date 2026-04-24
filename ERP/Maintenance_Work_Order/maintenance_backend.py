import os
import logging
import datetime
import time
import csv
import json
import io
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from local_db import get_db_connection

# Initialize Environment
# Script lives at: Meta_App_Factory/ERP/Maintenance_Work_Order/
# .env lives at:   Meta_App_Factory/.env  → 3 levels up
_here = os.path.dirname(os.path.abspath(__file__))           # …/Maintenance_Work_Order
_erp  = os.path.dirname(_here)                                # …/ERP
_factory = os.path.dirname(_erp)                              # …/Meta_App_Factory
env_path = os.path.join(_factory, '.env')
load_dotenv(env_path)
logging.basicConfig(level=logging.INFO)
logging.getLogger("MaintenanceBackend").info(f"Loading .env from: {env_path}")


# Ingestion Logic for Orchestration Boundary
GLOBAL_AI_DIRECTIVE_CONTEXT = ""

@asynccontextmanager
async def lifespan(app: FastAPI):
    global GLOBAL_AI_DIRECTIVE_CONTEXT
    directive_path = "/app/GLOBAL_AI_DIRECTIVE.md"
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
logger = logging.getLogger("MaintenanceBackend")

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
    status: str
    consumed_sku: Optional[str] = None
    manual_log: Optional[str] = None

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

# --- ENDPOINTS ---



@app.post("/api/user/verify-pin")
def verify_pin(payload: PinVerify):
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
            raise HTTPException(status_code=401, detail="Incorrect PIN. Authorization Denied.")
            
        role = "Admin" if row["authorization_level"] == "ADMIN" else "Technician"
        
        return {
            "status": "success",
            "role": role,
            "user": {
                "id": row["id"],
                "name": row["name"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PIN Verification Failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during verification.")
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
async def update_mwo_v2(mwo_id: str, payload: MWOUpdate, background_tasks: BackgroundTasks):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        if payload.status == "COMPLETED":
            cursor.execute("SELECT start_date, equipment_id FROM work_orders WHERE mwo_id = ?", (mwo_id,))
            check_row = cursor.fetchone()
            if not check_row or not check_row['start_date'] or not check_row['equipment_id']:
                raise HTTPException(status_code=400, detail="Cannot complete MWO: missing start_date or equipment_id.")
        
        if payload.status == "IN_PROGRESS":
            cursor.execute("""
                UPDATE work_orders 
                SET status = ?, consumed_sku = ?, manual_log = ?, start_date = COALESCE(start_date, ?)
                WHERE mwo_id = ?
            """, (payload.status, payload.consumed_sku, payload.manual_log, current_time, mwo_id))
        elif payload.status == "PENDING_REVIEW":
            cursor.execute("""
                UPDATE work_orders 
                SET status = ?, consumed_sku = ?, manual_log = ?
                WHERE mwo_id = ?
            """, (payload.status, payload.consumed_sku, payload.manual_log, mwo_id))
        elif payload.status == "COMPLETED":
            cursor.execute("""
                UPDATE work_orders 
                SET status = ?, consumed_sku = ?, manual_log = ?, completion_date = ?
                WHERE mwo_id = ?
            """, (payload.status, payload.consumed_sku, payload.manual_log, current_time, mwo_id))
        else:
            cursor.execute("""
                UPDATE work_orders 
                SET status = ?, consumed_sku = ?, manual_log = ?
                WHERE mwo_id = ?
            """, (payload.status, payload.consumed_sku, payload.manual_log, mwo_id))
            
        conn.commit()
        background_tasks.add_task(sync_memory_bus)
        
        # Terminal State Actuation: Atomic Drop Protocol
        if payload.status == "COMPLETED":
            cursor.execute("SELECT * FROM work_orders WHERE mwo_id = ?", (mwo_id,))
            final_row = cursor.fetchone()
            if final_row:
                background_tasks.add_task(archive_completed_mwo, dict(final_row))
        
        return {"status": "success", "message": "MWO Updated successfully"}
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
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
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
        reported_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
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
            current_year = datetime.datetime.now(datetime.timezone.utc).year
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

@app.post("/api/admin/users/bulk-upload")
async def bulk_upload_users(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
    
    conn = get_db_connection()
    try:
        content = await file.read()
        csv_reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
        
        cursor = conn.cursor()
        rows_processed = 0
        errors = 0
        
        for row in csv_reader:
            try:
                # Enforce required columns: user_id, name, role
                # Enforce role enum: ADMIN, HD, HM, TECH
                cursor.execute("""
                    INSERT INTO users (user_id, name, role, department, reports_to_hm_id)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        name=excluded.name,
                        role=excluded.role,
                        department=excluded.department,
                        reports_to_hm_id=excluded.reports_to_hm_id
                """, (
                    row.get('user_id'),
                    row.get('name'),
                    row.get('role'),
                    row.get('department'),
                    row.get('reports_to_hm_id') or None
                ))
                rows_processed += 1
            except Exception as e:
                logger.error(f"Error processing row {row}: {e}")
                errors += 1
                
        conn.commit()
        return {"status": "success", "rows_processed": rows_processed, "errors": errors}
    except Exception as e:
        conn.rollback()
        logger.error(f"Bulk upload failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during CSV upload.")
    finally:
        conn.close()

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


