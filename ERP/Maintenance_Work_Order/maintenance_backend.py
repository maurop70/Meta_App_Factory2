import os
import logging
import datetime
import csv
import io
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client, Client
from dotenv import load_dotenv

# Initialize Environment & Supabase
# Script lives at: Meta_App_Factory/ERP/Maintenance_Work_Order/
# .env lives at:   Meta_App_Factory/.env  → 3 levels up
_here = os.path.dirname(os.path.abspath(__file__))           # …/Maintenance_Work_Order
_erp  = os.path.dirname(_here)                                # …/ERP
_factory = os.path.dirname(_erp)                              # …/Meta_App_Factory
env_path = os.path.join(_factory, '.env')
load_dotenv(env_path)
logging.basicConfig(level=logging.INFO)
logging.getLogger("MaintenanceBackend").info(f"Loading .env from: {env_path}")
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# Supabase Initialization
supabase: Client = create_client(url, key)

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
    allow_origins=["*"],
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
    user_id: str
    pin: str

# --- SECURITY LAYER ---

def sanitize_user(user: dict) -> dict:
    """Strip pin_code from any user payload. Inject computed has_pin boolean."""
    has_pin = bool(user.get("pin_code"))
    sanitized = {k: v for k, v in user.items() if k != "pin_code"}
    sanitized["has_pin"] = has_pin
    return sanitized

# --- ENDPOINTS ---

@app.get("/api/hierarchy")
async def get_hierarchy():
    """Fetches full true relational hierarchy."""
    assets = supabase.table("erp_assets").select("*").execute()
    depts = supabase.table("erp_departments").select("*").execute()
    subdepts = supabase.table("erp_sub_departments").select("*").execute()
    return {
        "equipment": assets.data,
        "departments": depts.data,
        "sub_departments": subdepts.data
    }

@app.get("/api/users/search")
async def search_users(name: str = Query("")):
    response = supabase.table("erp_employees").select("*, erp_roles(*)").ilike("name", f"%{name}%").order("name").execute()
    return [sanitize_user(u) for u in response.data]

@app.post("/api/user/verify-pin")
async def verify_pin(payload: PinVerify):
    response = supabase.table("erp_employees").select("*, erp_roles(*)").eq("id", payload.user_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found.")
    user = response.data[0]
    if user.get("pin_code") and user.get("pin_code") != payload.pin:
        raise HTTPException(status_code=401, detail="Incorrect PIN.")
    return sanitize_user(user)

@app.post("/api/orders/submit")
async def submit_order(order: WorkOrderSubmit):
    try:
        data = {
            "reported_by": order.reported_by,
            "asset_id": order.asset_id,
            "issue_description": order.issue_description,
            "status": "PENDING",
            "reported_at": datetime.datetime.now().isoformat()
        }
        response = supabase.table("erp_maintenance_logs").insert(data).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        logger.error(f"Insert Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AssignUpdate(BaseModel):
    order_id: str
    technician_id: str

@app.post("/api/orders/assign")
async def assign_order(payload: AssignUpdate):
    response = supabase.table("erp_maintenance_logs").update({"assigned_to": payload.technician_id}).eq("id", payload.order_id).execute()
    return response.data

@app.post("/api/orders/update-status")
async def update_status(update: StatusUpdate):
    now = datetime.datetime.now().isoformat()
    update_payload = {"status": update.new_status}
    if update.new_status == "IN_PROGRESS":
        update_payload["started_at"] = now
        update_payload["resolution_notes"] = update.resolution_notes
    elif update.new_status == "PENDING_REVIEW":
        update_payload["resolution_notes"] = update.resolution_notes
    elif update.new_status == "COMPLETE":
        update_payload["completed_at"] = now
        if update.resolution_notes:
            # Append manager cost/notes if provided, or just keep existing from tech
            update_payload["resolution_notes"] = update.resolution_notes
            
    response = supabase.table("erp_maintenance_logs").update(update_payload).eq("id", update.order_id).execute()
    return response.data

@app.get("/api/orders/active")
async def get_active_orders():
    response = supabase.table("erp_maintenance_logs").select("*, erp_assets(*), erp_employees!reported_by(*)").neq("status", "COMPLETE").execute()
    return response.data

@app.get("/api/user/by-phone/{phone}")
async def user_by_phone(phone: str):
    """Query using top-level indexed phone_number column."""
    response = supabase.table("erp_employees").select("*, erp_roles(*)").eq("phone_number", phone).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Phone not found")
    return sanitize_user(response.data[0])

@app.get("/api/orders/assigned-to/{user_id}")
async def get_assigned_orders(user_id: str):
    """Query using top-level indexed assigned_to column."""
    response = supabase.table("erp_maintenance_logs").select("*, erp_assets(*), erp_employees!reported_by(*)").eq("assigned_to", user_id).neq("status", "COMPLETE").execute()
    return response.data

@app.get("/api/admin/users")
async def get_all_users():
    response = supabase.table("erp_employees").select("*, erp_roles(*)").execute()
    return [sanitize_user(u) for u in response.data]

@app.get("/api/admin/roles")
async def get_admin_roles():
    """Dynamic roles from the database — not hardcoded."""
    response = supabase.table("erp_roles").select("*").execute()
    return response.data

@app.post("/api/admin/user")
async def create_user(payload: UserSubmit):
    response = supabase.table("erp_employees").insert(payload.model_dump()).execute()
    return sanitize_user(response.data[0])

@app.post("/api/admin/equipment")
async def create_equipment(payload: EquipmentSubmit):
    response = supabase.table("erp_assets").insert(payload.model_dump()).execute()
    return response.data

@app.get("/api/department/{dept_id}/technicians")
async def get_dept_technicians(dept_id: str):
    response = supabase.table("erp_employees").select("*, erp_roles(*)").eq("authorization_level", "TECH").eq("department_id", dept_id).execute()
    return [sanitize_user(u) for u in response.data]

class DepartmentSubmit(BaseModel):
    department_name: str

class SubDepartmentSubmit(BaseModel):
    sub_dept_name: str
    department_id: str

@app.post("/api/admin/department")
async def create_department(payload: DepartmentSubmit):
    response = supabase.table("erp_departments").insert({"department_name": payload.department_name}).execute()
    return response.data

@app.post("/api/admin/sub-department")
async def create_sub_department(payload: SubDepartmentSubmit):
    response = supabase.table("erp_sub_departments").insert(payload.model_dump()).execute()
    return response.data

class RoutingUpdate(BaseModel):
    origin_dept_id: str
    target_dept_id: str

class SubRoutingUpdate(BaseModel):
    sub_dept_id: str
    target_dept_id: str

@app.post("/api/admin/department/routing")
async def set_dept_routing(payload: RoutingUpdate):
    """Sets the Universal Routing Matrix natively using servicing_department_id."""
    response = supabase.table("erp_departments").update({"servicing_department_id": payload.target_dept_id}).eq("department_id", payload.origin_dept_id).execute()
    return response.data

@app.post("/api/admin/department/routing/clear")
async def clear_dept_routing(payload: dict):
    origin_id = payload.get("origin_dept_id")
    response = supabase.table("erp_departments").update({"servicing_department_id": None}).eq("department_id", origin_id).execute()
    return response.data

@app.get("/api/notifications/unread/{user_id}/{dept_id}")
async def get_unread_notifications(user_id: str, dept_id: str):
    return []

@app.patch("/api/notifications/mark-read")
async def mark_notification_read():
    return {"status": "success"}

class UserInfoUpdate(BaseModel):
    id: str
    name: str
    role_id: Optional[str] = None
    department_id: Optional[str] = None

@app.patch("/api/admin/user/info")
async def update_user_info(payload: UserInfoUpdate):
    """Update employee name, role, and department assignment."""
    update_data = {"name": payload.name}
    if payload.role_id is not None:
        update_data["role_id"] = payload.role_id
    if payload.department_id is not None:
        update_data["department_id"] = payload.department_id
    response = supabase.table("erp_employees").update(update_data).eq("id", payload.id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found.")
    return sanitize_user(response.data[0])

@app.get("/api/admin/export/departments")
async def export_departments():
    response = supabase.table("erp_departments").select("*").execute()
    data = response.data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # STRICT SCHEMA ALIGNMENT
    writer.writerow(["department_id", "department_name", "created_at"])
    
    for row in data:
        writer.writerow([row.get("department_id", ""), row.get("department_name", ""), row.get("created_at", "")])
        
    output.seek(0)
    return StreamingResponse(
        output, 
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment; filename=maf_departments_export.csv"}
    )

@app.post("/api/admin/import/departments")
async def import_departments(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Catastrophic Failure: Target must be a .csv file.")
        
    contents = await file.read()
    decoded = contents.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    
    success_count = 0
    for row in reader:
        dept_name = row.get("department_name")
        if not dept_name:
            continue
            
        payload = {"department_name": dept_name}
        
        # STRICT SCHEMA ALIGNMENT
        dept_id = row.get("department_id", "").strip()
        
        if dept_id:
            payload["department_id"] = dept_id
            supabase.table("erp_departments").upsert(payload).execute()
        else:
            supabase.table("erp_departments").insert(payload).execute()
            
        success_count += 1
        
    return {"status": "success", "rows_processed": success_count}

# --- SUB-DEPARTMENTS (LINE/ZONE) ---
@app.get("/api/admin/export/sub_departments")
async def export_sub_departments():
    response = supabase.table("erp_sub_departments").select("*").execute()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["sub_department_id", "sub_department_name", "department_id", "created_at"])
    for row in response.data:
        writer.writerow([row.get("sub_department_id", ""), row.get("sub_department_name", ""), row.get("department_id", ""), row.get("created_at", "")])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=maf_lines_export.csv"})

@app.post("/api/admin/import/sub_departments")
async def import_sub_departments(file: UploadFile = File(...)):
    reader = csv.DictReader(io.StringIO((await file.read()).decode('utf-8')))
    success = 0
    for row in reader:
        if not row.get("sub_department_name"): continue
        payload = {"sub_department_name": row.get("sub_department_name"), "department_id": row.get("department_id")}
        pk = row.get("sub_department_id", "").strip()
        if pk: payload["sub_department_id"] = pk
        supabase.table("erp_sub_departments").upsert(payload).execute() if pk else supabase.table("erp_sub_departments").insert(payload).execute()
        success += 1
    return {"status": "success", "rows_processed": success}

# --- ROLES ---
@app.get("/api/admin/export/roles")
async def export_roles():
    response = supabase.table("erp_roles").select("*").execute()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["role_id", "role_name", "can_submit", "can_manage", "can_execute", "created_at"])
    for row in response.data:
        writer.writerow([row.get("role_id", ""), row.get("role_name", ""), row.get("can_submit", ""), row.get("can_manage", ""), row.get("can_execute", ""), row.get("created_at", "")])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=maf_roles_export.csv"})

@app.post("/api/admin/import/roles")
async def import_roles(file: UploadFile = File(...)):
    reader = csv.DictReader(io.StringIO((await file.read()).decode('utf-8')))
    success = 0
    for row in reader:
        if not row.get("role_name"): continue
        payload = {
            "role_name": row.get("role_name"), 
            "can_submit": str(row.get("can_submit")).lower() in ['true', '1', 't', 'y', 'yes'],
            "can_manage": str(row.get("can_manage")).lower() in ['true', '1', 't', 'y', 'yes'],
            "can_execute": str(row.get("can_execute")).lower() in ['true', '1', 't', 'y', 'yes']
        }
        pk = row.get("role_id", "").strip()
        if pk: payload["role_id"] = pk
        supabase.table("erp_roles").upsert(payload).execute() if pk else supabase.table("erp_roles").insert(payload).execute()
        success += 1
    return {"status": "success", "rows_processed": success}

# --- ASSETS (EQUIPMENT) ---
@app.get("/api/admin/export/assets")
async def export_assets():
    response = supabase.table("erp_assets").select("*").execute()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["asset_id", "machine_name", "department_id", "sub_department_id", "created_at"])
    for row in response.data:
        writer.writerow([row.get("asset_id", ""), row.get("machine_name", ""), row.get("department_id", ""), row.get("sub_department_id", ""), row.get("created_at", "")])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=maf_assets_export.csv"})

@app.post("/api/admin/import/assets")
async def import_assets(file: UploadFile = File(...)):
    reader = csv.DictReader(io.StringIO((await file.read()).decode('utf-8')))
    success = 0
    for row in reader:
        if not row.get("machine_name"): continue
        payload = {"machine_name": row.get("machine_name"), "department_id": row.get("department_id")}
        if row.get("sub_department_id"): payload["sub_department_id"] = row.get("sub_department_id")
        pk = row.get("asset_id", "").strip()
        if pk: payload["asset_id"] = pk
        supabase.table("erp_assets").upsert(payload).execute() if pk else supabase.table("erp_assets").insert(payload).execute()
        success += 1
    return {"status": "success", "rows_processed": success}

# --- PERSONNEL (EMPLOYEES) ---
@app.get("/api/admin/export/employees")
async def export_employees():
    response = supabase.table("erp_employees").select("*").execute()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["employee_id", "name", "phone", "pin_code", "role_id", "department_id", "created_at"])
    for row in response.data:
        writer.writerow([row.get("employee_id", ""), row.get("name", ""), row.get("phone", ""), row.get("pin_code", ""), row.get("role_id", ""), row.get("department_id", ""), row.get("created_at", "")])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=maf_personnel_export.csv"})

@app.post("/api/admin/import/employees")
async def import_employees(file: UploadFile = File(...)):
    reader = csv.DictReader(io.StringIO((await file.read()).decode('utf-8')))
    success = 0
    for row in reader:
        if not row.get("name"): continue
        payload = {"name": row.get("name"), "phone": row.get("phone"), "pin_code": row.get("pin_code"), "role_id": row.get("role_id"), "department_id": row.get("department_id")}
        pk = row.get("employee_id", "").strip()
        if pk: payload["employee_id"] = pk
        supabase.table("erp_employees").upsert(payload).execute() if pk else supabase.table("erp_employees").insert(payload).execute()
        success += 1
    return {"status": "success", "rows_processed": success}
