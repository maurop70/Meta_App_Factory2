import os
import logging
import datetime
import time
import csv
import json
import io
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

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


app = FastAPI(title="Maintenance Work Order API - Global ERP Connected")
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

@app.patch("/api/mwo/{mwo_id}")
async def update_mwo_v2(mwo_id: str, payload: MWOUpdate):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        current_time = time.time()
        
        if payload.status == "IN_PROGRESS":
            cursor.execute("""
                UPDATE work_orders 
                SET status = ?, consumed_sku = ?, manual_log = ?, execution_start = COALESCE(execution_start, ?)
                WHERE mwo_id = ?
            """, (payload.status, payload.consumed_sku, payload.manual_log, current_time, mwo_id))
        elif payload.status == "PENDING_REVIEW":
            cursor.execute("""
                UPDATE work_orders 
                SET status = ?, consumed_sku = ?, manual_log = ?, execution_end = ?
                WHERE mwo_id = ?
            """, (payload.status, payload.consumed_sku, payload.manual_log, current_time, mwo_id))
        elif payload.status == "COMPLETED":
            cursor.execute("""
                UPDATE work_orders 
                SET status = ?, consumed_sku = ?, manual_log = ?, completed_at = ?
                WHERE mwo_id = ?
            """, (payload.status, payload.consumed_sku, payload.manual_log, current_time, mwo_id))
        else:
            cursor.execute("""
                UPDATE work_orders 
                SET status = ?, consumed_sku = ?, manual_log = ?
                WHERE mwo_id = ?
            """, (payload.status, payload.consumed_sku, payload.manual_log, mwo_id))
            
        conn.commit()
        
        # Terminal State Actuation: Atomic Drop Protocol
        if payload.status == "COMPLETED":
            cursor.execute("SELECT * FROM work_orders WHERE mwo_id = ?", (mwo_id,))
            final_row = cursor.fetchone()
            if final_row:
                archival_payload = {
                    "document_type": "MWO_REPORT",
                    "payload": dict(final_row)
                }
                
                queue_dir = os.path.join(_factory, "Universal_Memory", "Archival_Queue")
                os.makedirs(queue_dir, exist_ok=True)
                
                tmp_path = os.path.join(queue_dir, f"{mwo_id}.tmp")
                final_path = os.path.join(queue_dir, f"{mwo_id}.json")
                
                with open(tmp_path, 'w') as f:
                    json.dump(archival_payload, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                    
                os.replace(tmp_path, final_path)
        
        return {"status": "success", "message": "MWO Updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update MWO {mwo_id}: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Internal server error while updating MWO.")
    finally:
        if conn:
            conn.close()

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


