import os
import datetime
from fastapi import FastAPI, HTTPException
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
    department_ref_id: str  # NEW FIELD
    equipment_id: str
    pm_urgency_level: str
    risk_level: str
    maintenance_type: str
    problem_description: str

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
    role: str
    department_ref_id: str

class EquipmentSubmit(BaseModel):
    equipment_name: str
    department_ref_id: str

@app.get("/")
async def serve_frontend():
    """Serves the Progressive Web App UI."""
    return FileResponse("index.html")

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

@app.post("/api/orders/submit")
async def submit_order(order: WorkOrderSubmit):
    """PM submits a new order. Engine attempts auto-assignment."""
    data = order.dict()
    data["status"] = "Submitted"
    
    # 1. Fetch the Department Manager
    dept_res = supabase.table("departments").select("manager_id").eq("department_id", data["department_ref_id"]).execute()
    manager_id = dept_res.data[0].get("manager_id") if dept_res.data else None
    
    # 2. Check for subordinate Technicians in this department
    techs_res = supabase.table("app_users").select("user_id").eq("department_ref_id", data["department_ref_id"]).eq("role", "Tech").execute()
    
    # 3. Auto-Assign Logic: If no techs exist, assign directly to the Manager
    if not techs_res.data and manager_id:
        data["technician_id"] = manager_id

    response = supabase.table("work_orders").insert(data).execute()
    return {"status": "success", "data": response.data}

@app.post("/api/orders/assign")
async def assign_order(payload: dict):
    """Allows the Manager to delegate a ticket to a specific technician."""
    order_id = payload.get("order_id")
    tech_id = payload.get("technician_id")
    response = supabase.table("work_orders").update({"technician_id": tech_id}).eq("order_id", order_id).execute()
    return response.data

@app.get("/api/department/{dept_id}/technicians")
async def get_technicians(dept_id: str):
    """Fetches the roster of mechanics for the Manager's delegation dropdown."""
    response = supabase.table("app_users").select("*").eq("department_ref_id", dept_id).in_("role", ["Tech", "Manager"]).execute()
    return response.data

@app.get("/api/orders/active")
async def get_active_orders():
    """Fetches the active feed, now including the source department for routing."""
    response = supabase.table("work_orders").select(
        "*, app_users!pm_user_id(*), equipment_registry(*), departments(*)"
    ).eq("is_archived", False).order("hm_execution_index", desc=False).execute()
    return response.data

@app.post("/api/orders/update-status")
async def update_status(update: StatusUpdate):
    """The 3-Button State Machine Logic."""
    now = datetime.datetime.now().isoformat()
    update_payload = {"status": update.new_status}
    
    if update.new_status == "In Process":
        update_payload["start_date"] = now
        
    elif update.new_status == "Pending Review":
        update_payload["work_performed"] = update.work_performed
        
    elif update.new_status == "Complete":
        update_payload["completion_date"] = now
        update_payload["cost"] = update.cost
        update_payload["reviewed_by"] = update.user_id
        update_payload["is_archived"] = True
        
        # Execute Supabase Update first to get timestamps
        supa_res = supabase.table("work_orders").update(update_payload).eq("order_id", update.order_id).execute()
        
        # Trigger Native PDF Archival
        if supa_res.data:
            generate_pdf_receipt(supa_res.data)
            return {"status": "Archived successfully", "data": supa_res.data}

    # Standard Status Update
    response = supabase.table("work_orders").update(update_payload).eq("order_id", update.order_id).execute()
    return response.data

@app.post("/api/admin/department")
async def add_department(dept: DepartmentSubmit):
    response = supabase.table("departments").insert([{"department_name": dept.department_name}]).execute()
    return {"status": "success", "data": response.data}

@app.post("/api/admin/user")
async def add_user(user: UserSubmit):
    response = supabase.table("app_users").insert([user.dict()]).execute()
    return {"status": "success", "data": response.data}

@app.post("/api/admin/equipment")
async def add_equipment(equip: EquipmentSubmit):
    response = supabase.table("equipment_registry").insert([equip.dict()]).execute()
    return {"status": "success", "data": response.data}

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
