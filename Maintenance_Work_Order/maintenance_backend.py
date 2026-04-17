import os
import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from supabase import create_client, Client
from fpdf import FPDF
from dotenv import load_dotenv

# Initialize Environment & Supabase
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# Monkey-patch older Supabase validation for newer API key formats
import supabase._sync.client as supabase_client_mod
import re
original_match = re.match
supabase_client_mod.re.match = lambda *args, **kwargs: True

supabase: Client = create_client(url, key)

# Restore regex
supabase_client_mod.re.match = original_match

app = FastAPI(title="Maintenance Work Order API")

# Define Data Models
class WorkOrderSubmit(BaseModel):
    pm_user_id: str
    department_ref_id: str
    sub_dept_id: Optional[str] = None
    equipment_id: str
    pm_urgency_level: str
    risk_level: str
    maintenance_type: str
    problem_description: str
    target_department_id: Optional[str] = None

class StatusUpdate(BaseModel):
    order_id: str
    new_status: str
    user_id: str # To verify permissions or log who did it
    work_performed: str = ""
    cost: float = 0.0

class DepartmentSubmit(BaseModel):
    department_name: str

class UserSubmit(BaseModel):
    full_name: str
    phone_number: str
    role_id: str   # Normalized: using UUID instead of string
    department_ref_id: str
    pin_code: str = ""

class EquipmentSubmit(BaseModel):
    equipment_name: str
    department_ref_id: str
    sub_dept_ref_id: Optional[str] = None

class UserInfoUpdate(BaseModel):
    user_id: str
    full_name: str
    role_id: str
    department_ref_id: str

class PhoneUpdate(BaseModel):
    user_id: str
    phone_number: str

class RoleSubmit(BaseModel):
    role_name: str
    can_submit: bool = False
    can_manage: bool = False
    can_execute: bool = False

class RoleUpdate(BaseModel):
    role_id: str
    can_submit: bool = False
    can_manage: bool = False
    can_execute: bool = False

class DepartmentUpdate(BaseModel):
    department_id: str
    servicing_department_id: Optional[str] = None

class ManagerUpdate(BaseModel):
    department_id: str
    manager_id: str

class SubDeptSubmit(BaseModel):
    sub_dept_name: str
    department_id: str  # parent department FK

class SubDeptRoutingUpdate(BaseModel):
    sub_dept_id: str
    servicing_department_id: Optional[str] = None

class PinVerify(BaseModel):
    user_id: str
    pin: str

class PinUpdate(BaseModel):
    user_id: str
    pin_code: str

class NotificationLog(BaseModel):
    order_id: str
    event_type: str
    origin_dept_id: Optional[str] = None
    target_dept_id: Optional[str] = None
    target_user_id: Optional[str] = None # Added for precision targeting
    message: str

# --- HELPERS ---

def log_history(order_id: str, status: str, user_id: str, note: str = ""):
    """Logs a state transition into the work_order_history table."""
    try:
        supabase.table("work_order_history").insert({
            "order_id": order_id,
            "status": status,
            "user_id": user_id,
            "note": note,
            "timestamp": datetime.datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"History Log Failed: {e}")

def dispatch_event(event: NotificationLog):
    """Native Event Dispatcher: logs a high-priority event to the app_notifications ledger."""
    try:
        supabase.table("app_notifications").insert(event.dict()).execute()
    except Exception as e:
        print(f"Event Dispatch Failed: {e}")

async def has_permission(user_id: str, permission: str) -> bool:
    """Checks if a user has a specific permission via their role."""
    res = supabase.table("app_users").select("roles!role_id(*)").eq("user_id", user_id).execute()
    if not res.data: return False
    role_data = res.data[0].get("roles")
    if not role_data: return False
    return role_data.get(permission, False)

# --- ENDPOINTS ---

@app.get("/api/hierarchy")
async def get_hierarchy():
    """Fetches Departments, Sub-Departments, and Equipment for cascading dropdowns."""
    depts = supabase.table("departments").select("*").eq("is_active", True).execute()
    sub_depts = supabase.table("sub_departments").select("*").eq("is_active", True).execute()
    equip = supabase.table("equipment_registry").select("*").eq("is_active", True).execute()
    
    return {
        "departments": depts.data,
        "sub_departments": sub_depts.data,
        "equipment": equip.data
    }

@app.get("/api/user/by-phone/{phone}")
async def get_user_by_phone(phone: str):
    """Identifies a user by their registered phone number with native role join."""
    response = supabase.table("app_users").select(
        "*, roles!role_id(*)"
    ).eq("phone_number", phone).eq("is_active", True).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="No active user found with this phone number.")
    
    user = response.data[0]
    # Flatten role permissions from the native join
    role_data = user.pop("roles", {})
    if role_data:
        # Supabase returns a list for joins if not 1:1, but typically it's an object if linked correctly
        if isinstance(role_data, list): role_data = role_data[0] if role_data else {}
        user.update({
            "can_submit": role_data.get("can_submit", False),
            "can_manage": role_data.get("can_manage", False),
            "can_execute": role_data.get("can_execute", False)
        })
    return user

@app.get("/api/users/search")
async def search_users(name: str = Query("")):
    """Desktop login: live name-search. Returns has_pin flag — never returns the actual pin_code."""
    response = supabase.table("app_users").select(
        "user_id, full_name, role, department_ref_id, phone_number, pin_code"
    ).eq("is_active", True).ilike("full_name", f"%{name}%").order("full_name").execute()
    users = []
    for u in response.data:
        u["has_pin"] = bool(u.get("pin_code"))
        u.pop("pin_code", None)   # never expose the PIN
        users.append(u)
    return users

@app.post("/api/user/verify-pin")
async def verify_pin(payload: PinVerify):
    """Desktop login with native role join and permission flag injection."""
    response = supabase.table("app_users").select(
        "*, roles!role_id(*)"
    ).eq("user_id", payload.user_id).eq("is_active", True).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user = response.data[0]
    stored_pin = user.get("pin_code") or ""
    if stored_pin and stored_pin != payload.pin:
        raise HTTPException(status_code=401, detail="Incorrect PIN.")
    
    # Flatten role permissions from the join
    role_data = user.pop("roles", {})
    if role_data:
        if isinstance(role_data, list): role_data = role_data[0] if role_data else {}
        user.update({
            "can_submit": role_data.get("can_submit", False),
            "can_manage": role_data.get("can_manage", False),
            "can_execute": role_data.get("can_execute", False)
        })
    user.pop("pin_code", None)
    return user

@app.post("/api/orders/submit")
async def submit_order(order: WorkOrderSubmit):
    """PM submits a new order. Engine attempts auto-assignment based on Servicing Department Matrix."""
    try:
        data = order.dict()
        data["status"] = "Submitted"
        
        # 1. Determine Target Department based on Hierarchy Matrix
        # Order of Precedence: Sub-Department (Line) Specific Routing -> Department Generic Routing -> Origin Dept (Self-Route)
        
        # Check Sub-Department Override
        target_dept_id = None
        sub_dept_id_val = data.pop("sub_dept_id", None)
        if sub_dept_id_val:
            sub_res = supabase.table("sub_departments").select("servicing_department_id").eq("sub_dept_id", sub_dept_id_val).execute()
            if sub_res.data and sub_res.data[0].get("servicing_department_id"):
                target_dept_id = sub_res.data[0].get("servicing_department_id")

        if not target_dept_id:
            # Fallback to Department Generic Routing
            origin_dept = supabase.table("departments").select("servicing_department_id").eq("department_id", data["department_ref_id"]).execute()
            target_dept_id = origin_dept.data[0].get("servicing_department_id") if (origin_dept.data and origin_dept.data[0].get("servicing_department_id")) else data["department_ref_id"]
        
        # 2. Fetch the Manager of the Target Department
        dept_res = supabase.table("departments").select("manager_id").eq("department_id", target_dept_id).execute()
        manager_id = dept_res.data[0].get("manager_id") if dept_res.data else None
        
        # 3. Check for technicians in the Target Department who can execute
        techs_res = supabase.table("app_users").select("user_id").eq("department_ref_id", target_dept_id).eq("role", "Tech").execute()
        
        # 4. Auto-Assign Logic: If no techs exist, assign directly to the Manager
        if not techs_res.data and manager_id:
            data["technician_id"] = manager_id
            
        # Update order to reflect it's being handled by the target department
        data["target_department_id"] = target_dept_id 

        response = supabase.table("work_orders").insert(data).execute()
        
        # 5. Dispatch Native Event for Urgent/Critical Tickets
        if response.data and order.pm_urgency_level in ["Critical", "Urgent"]:
            dispatch_event(NotificationLog(
                order_id=response.data[0].get("order_id"),
                event_type="URGENT_TICKET",
                origin_dept_id=data["department_ref_id"],
                target_dept_id=target_dept_id,
                message=f"Urgent {order.pm_urgency_level} ticket for {order.problem_description[:50]}..."
            ))

        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Insert Failed: {str(e)}")

@app.post("/api/orders/assign")
async def assign_order(payload: dict):
    """Allows the Manager to delegate a ticket to a specific technician with native alert."""
    order_id = payload.get("order_id")
    tech_id = payload.get("technician_id")
    response = supabase.table("work_orders").update({"technician_id": tech_id}).eq("order_id", order_id).execute()
    
    if response.data and tech_id:
        # Fetch order details for the notification message
        order = response.data[0]
        dispatch_event(NotificationLog(
            order_id=order_id,
            event_type="ASSIGNMENT",
            target_user_id=tech_id,
            message=f"New Assignment: You have been assigned to ticket #{order_id[:8]}"
        ))
    return response.data

@app.get("/api/department/{dept_id}/technicians")
async def get_technicians(dept_id: str):
    """Fetches the roster of personnel for the Manager's delegation dropdown."""
    if not dept_id or dept_id == "null":
        return []
    # Fetch all active users in the department with their role permissions
    response = supabase.table("app_users").select(
        "*, roles!role_id(*)"
    ).eq("department_ref_id", dept_id).eq("is_active", True).execute()
    
    # Return users who have 'can_execute' permission or the legacy 'Tech' role
    techs = []
    for u in response.data:
        role_data = u.get("roles")
        # Handle cases where roles might be a list or a single object
        if isinstance(role_data, list): role_data = role_data[0] if role_data else {}
        
        if (role_data and role_data.get("can_execute")) or u.get("role") == "Tech":
            techs.append(u)
    return techs

@app.get("/api/orders/active")
async def get_active_orders(department_id: Optional[str] = Query(None)):
    """Fetches active feed. Optionally scoped to a department (for manager view)."""
    # Use explicit relationship mapping for all joined tables
    query = supabase.table("work_orders").select(
        "*, app_users!pm_user_id(*), equipment_registry(*), departments!department_ref_id(*)"
    ).eq("is_archived", False).order("hm_execution_index", desc=False)
    
    # Sanitize: Treat empty string as no filter (Admin global view)
    if department_id and department_id.strip() and department_id != "undefined":
        # The Manager should see tickets routed TO their department
        query = query.or_(f"target_department_id.eq.{department_id},department_ref_id.eq.{department_id}")
        
    response = query.execute()
    return response.data

@app.get("/api/orders/assigned-to/{user_id}")
async def get_orders_assigned_to(user_id: str):
    """Fetches all active orders assigned to a specific technician."""
    response = supabase.table("work_orders").select(
        "*, equipment_registry(*), departments!department_ref_id(*)"
    ).eq("technician_id", user_id).eq("is_archived", False).order("hm_execution_index", desc=False).execute()
    return response.data

@app.post("/api/orders/update-status")
async def update_status(update: StatusUpdate):
    """The 3-Button State Machine Logic with History Logging."""
    now = datetime.datetime.now().isoformat()
    update_payload = {"status": update.new_status}
    
    if update.new_status == "In Process":
        update_payload["start_date"] = now
        update_payload["work_performed"] = ""
        
    elif update.new_status == "Pending Review":
        update_payload["work_performed"] = update.work_performed
        
    elif update.new_status == "Complete":
        update_payload["completion_date"] = now
        update_payload["cost"] = update.cost
        update_payload["reviewed_by"] = update.user_id
        update_payload["is_archived"] = True
        
        supa_res = supabase.table("work_orders").update(update_payload).eq("order_id", update.order_id).execute()
        if supa_res.data:
            log_history(update.order_id, update.new_status, update.user_id, "Final review and sign-off.")
            generate_pdf_receipt(supa_res.data[0])
            return {"status": "Archived successfully", "data": supa_res.data}

    response = supabase.table("work_orders").update(update_payload).eq("order_id", update.order_id).execute()
    if response.data:
        log_history(update.order_id, update.new_status, update.user_id, update.work_performed)
    return response.data

@app.get("/")
async def serve_frontend():
    """Serves the Progressive Web App UI."""
    return FileResponse("index.html")

@app.get("/api/admin/roles")
async def get_roles():
    """Fetches all active roles for the dynamic personnel dropdown."""
    response = supabase.table("roles").select("*").eq("is_active", True).order("role_name").execute()
    return response.data

@app.post("/api/admin/role")
async def add_role(role: RoleSubmit):
    """Adds a new custom role to the system with dynamic permissions."""
    try:
        response = supabase.table("roles").insert([role.dict()]).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/admin/role/permissions")
async def update_role_permissions(payload: RoleUpdate):
    """Updates the permissions of an existing role."""
    response = supabase.table("roles").update({
        "can_submit": payload.can_submit,
        "can_manage": payload.can_manage,
        "can_execute": payload.can_execute
    }).eq("role_id", payload.role_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Role not found.")
    return {"status": "success", "data": response.data}

@app.post("/api/admin/department")
async def add_department(dept: DepartmentSubmit):
    response = supabase.table("departments").insert([{"department_name": dept.department_name}]).execute()
    return {"status": "success", "data": response.data}

@app.post("/api/admin/sub-department")
async def add_sub_department(sub: SubDeptSubmit):
    """Adds a new Production Line/Zone linked to a parent department."""
    try:
        response = supabase.table("sub_departments").insert([{
            "sub_dept_name": sub.sub_dept_name,
            "department_id": sub.department_id
        }]).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/admin/user")
async def add_user(user: UserSubmit):
    response = supabase.table("app_users").insert([user.dict()]).execute()
    return {"status": "success", "data": response.data}

@app.post("/api/admin/equipment")
async def add_equipment(equip: EquipmentSubmit):
    response = supabase.table("equipment_registry").insert([equip.dict()]).execute()
    return {"status": "success", "data": response.data}

@app.get("/api/admin/users")
async def get_all_users():
    """Fetches all personnel for the Admin Console update panel."""
    # Ensure role_id is selected so we can edit it properly
    response = supabase.table("app_users").select("user_id, full_name, role, role_id, department_ref_id, phone_number").eq("is_active", True).order("full_name").execute()
    return response.data

@app.patch("/api/admin/user/info")
async def update_user_info(payload: UserInfoUpdate):
    """Updates core identity info for a user (Name, Role, Dept)."""
    # Fetch the role name so we can also update the legacy 'role' column just in case
    role_res = supabase.table("roles").select("role_name").eq("role_id", payload.role_id).execute()
    role_name = role_res.data[0].get("role_name") if role_res.data else ""

    response = supabase.table("app_users").update({
        "full_name": payload.full_name,
        "role_id": payload.role_id,
        "role": role_name,
        "department_ref_id": payload.department_ref_id
    }).eq("user_id", payload.user_id).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"status": "success", "data": response.data}

@app.patch("/api/admin/user/phone")
async def update_user_phone(payload: PhoneUpdate):
    """Updates the phone number for an existing user."""
    response = supabase.table("app_users").update({"phone_number": payload.phone_number}).eq("user_id", payload.user_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found or no change made.")
    return {"status": "success", "data": response.data}

@app.patch("/api/admin/user/pin")
async def update_user_pin(payload: PinUpdate):
    """Updates a user's 4-digit desktop PIN from Admin Console."""
    if not payload.pin_code.isdigit() or len(payload.pin_code) != 4:
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits.")
    response = supabase.table("app_users").update({"pin_code": payload.pin_code}).eq("user_id", payload.user_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"status": "success"}

# --- RECORD ARCHIVE ENDPOINTS ---

@app.patch("/api/admin/user/{user_id}/archive")
async def archive_user(user_id: str):
    """Terminates a user — sets is_active=False, removing them from all active dropdowns."""
    response = supabase.table("app_users").update({"is_active": False}).eq("user_id", user_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"status": "archived", "data": response.data}

@app.patch("/api/admin/department/routing")
async def update_routing(payload: DepartmentUpdate):
    """Updates the servicing department for a specific origin department."""
    response = supabase.table("departments").update({
        "servicing_department_id": payload.servicing_department_id
    }).eq("department_id", payload.department_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Department not found.")
    return {"status": "success", "data": response.data}

@app.patch("/api/admin/department/routing/clear")
async def clear_routing(payload: DepartmentUpdate):
    """Clears the servicing department for an origin department."""
    response = supabase.table("departments").update({
        "servicing_department_id": None
    }).eq("department_id", payload.department_id).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail=f"Department {payload.department_id} not found.")
    
    return {"status": "success", "data": response.data}

@app.patch("/api/admin/sub-department/routing")
async def update_sub_routing(payload: SubDeptRoutingUpdate):
    """Updates the servicing department override for a specific production line/zone."""
    response = supabase.table("sub_departments").update({
        "servicing_department_id": payload.servicing_department_id
    }).eq("sub_dept_id", payload.sub_dept_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Production Line/Zone not found.")
    return {"status": "success", "data": response.data}

@app.patch("/api/admin/sub-department/routing/clear")
async def clear_sub_routing(payload: SubDeptRoutingUpdate):
    """Clears the servicing department override for a specific production line/zone."""
    response = supabase.table("sub_departments").update({
        "servicing_department_id": None
    }).eq("sub_dept_id", payload.sub_dept_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Production Line/Zone not found.")
    return {"status": "success", "data": response.data}

@app.patch("/api/admin/department/manager")
async def update_manager(payload: ManagerUpdate):
    """Assigns a manager_id to a specific department."""
    response = supabase.table("departments").update({
        "manager_id": payload.manager_id
    }).eq("department_id", payload.department_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Department not found.")
    return {"status": "success", "data": response.data}

@app.patch("/api/admin/department/{department_id}/archive")
async def archive_department(department_id: str):
    """Archives a department — sets is_active=False, removing it from all active dropdowns."""
    response = supabase.table("departments").update({"is_active": False}).eq("department_id", department_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Department not found.")
    return {"status": "archived", "data": response.data}

@app.patch("/api/admin/role/{role_id}/archive")
async def archive_role(role_id: str):
    """Archives a role — sets is_active=False, removing it from the personnel role dropdown."""
    response = supabase.table("roles").update({"is_active": False}).eq("role_id", role_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Role not found.")
    return {"status": "archived", "data": response.data}

@app.patch("/api/admin/sub-department/{sub_dept_id}/archive")
async def archive_sub_department(sub_dept_id: str):
    """Archives a Production Line/Zone — sets is_active=False, removing it from the PM Submit dropdown."""
    response = supabase.table("sub_departments").update({"is_active": False}).eq("sub_dept_id", sub_dept_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Production Line/Zone not found.")
    return {"status": "archived", "data": response.data}

@app.get("/api/notifications/unread/{user_id}/{dept_id}")
async def get_unread_notifications(user_id: str, dept_id: str):
    """Fetches all unread high-priority events for the user (personal or department-wide)."""
    # Use 'or' to fetch both personal assignments and department-wide manager alerts
    response = supabase.table("app_notifications").select("*").or_(
        f"target_user_id.eq.{user_id},target_dept_id.eq.{dept_id}"
    ).eq("is_read", False).order("created_at", desc=True).execute()
    return response.data

@app.patch("/api/notifications/mark-read")
async def mark_notification_read(payload: dict):
    """Clears a notification from the active alert queue."""
    notification_id = payload.get("notification_id")
    response = supabase.table("app_notifications").update({"is_read": True}).eq("notification_id", notification_id).execute()
    return response.data

# --- ARCHIVAL ENGINE ---

def generate_pdf_receipt(order_data):
    """Calculates Cycle Time and generates the immutable PDF receipt."""
    # 1. Calculate Cycle Time
    start = datetime.datetime.fromisoformat(order_data.get('start_date', ''))
    end = datetime.datetime.fromisoformat(order_data.get('completion_date', ''))
    cycle_time_days = round((end - start).total_seconds() / 86400, 2) if start and end else "N/A"

    # 2. Render PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="MAINTENANCE WORK ORDER RECEIPT", ln=1, align='C')
    pdf.set_font("Arial", size=12)
    pdf.line(10, 25, 200, 25)
    
    # Body Data
    pdf.cell(200, 10, txt=f"Order ID: {order_data.get('order_id')}", ln=1)
    pdf.cell(200, 10, txt=f"Urgency: {order_data.get('pm_urgency_level')} | Risk: {order_data.get('risk_level')}", ln=1)
    pdf.cell(200, 10, txt=f"Description: {order_data.get('problem_description')}", ln=1)
    pdf.line(10, 60, 200, 60)
    
    # Execution Data
    pdf.cell(200, 10, txt=f"Work Performed: {order_data.get('work_performed', 'N/A')}", ln=1)
    pdf.cell(200, 10, txt=f"Cycle Time: {cycle_time_days} Days", ln=1)
    pdf.cell(200, 10, txt=f"Material Cost: ${order_data.get('cost', '0.00')}", ln=1)
    
    # Save natively
    filename = f"maintenance_archives/WO_{order_data.get('order_id')}.pdf"
    pdf.output(filename)
