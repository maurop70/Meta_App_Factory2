import sqlite3
import os
import uuid
import bcrypt

DB_PATH = r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Module_0_Gateway\data\gateway_core.db"

def seed_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create Tables
    cursor.execute('''
    CREATE TABLE erp_departments (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )''')
    
    cursor.execute('''
    CREATE TABLE erp_employees (
        id TEXT PRIMARY KEY,
        emp_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        first_name TEXT,
        last_name TEXT,
        role TEXT NOT NULL,
        pin TEXT,
        pin_hash TEXT,
        is_active INTEGER DEFAULT 1,
        department_id TEXT,
        reports_to_hm_id TEXT,
        status TEXT DEFAULT 'ACTIVE',
        department TEXT,
        FOREIGN KEY(department_id) REFERENCES erp_departments(id),
        FOREIGN KEY(reports_to_hm_id) REFERENCES erp_employees(id)
    )''')
    
    # Seed Departments
    deps = [
        ("DEPT-001", "Dispatch Command"),
        ("DEPT-002", "Field Maintenance"),
        ("DEPT-003", "IT Infrastructure"),
        ("DEPT-004", "Procurement")
    ]
    cursor.executemany("INSERT INTO erp_departments (id, name) VALUES (?, ?)", deps)
    
    # Seed Core Accounts
    # Admin
    admin_id = f"U-{uuid.uuid4().hex[:6].upper()}"
    admin_pin = "1234"
    admin_hash = bcrypt.hashpw(admin_pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # HM
    hm_id = f"U-{uuid.uuid4().hex[:6].upper()}"
    hm_pin = "2345"
    hm_hash = bcrypt.hashpw(hm_pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Tech
    tech_id = f"U-{uuid.uuid4().hex[:6].upper()}"
    tech_pin = "3456"
    tech_hash = bcrypt.hashpw(tech_pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    employees = [
        (admin_id, "ERP-1000", "System Administrator", "System", "Administrator", "ADMINISTRATOR", admin_pin, admin_hash, 1, "DEPT-003", None, "ACTIVE", "IT Infrastructure"),
        (hm_id, "ERP-2000", "Hub Manager", "Hub", "Manager", "HM", hm_pin, hm_hash, 1, "DEPT-001", None, "ACTIVE", "Dispatch Command"),
        (tech_id, "ERP-3000", "Field Technician", "Field", "Technician", "TECHNICIAN", tech_pin, tech_hash, 1, "DEPT-002", hm_id, "ACTIVE", "Field Maintenance")
    ]
    
    cursor.executemany("""
    INSERT INTO erp_employees 
    (id, emp_id, name, first_name, last_name, role, pin, pin_hash, is_active, department_id, reports_to_hm_id, status, department) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, employees)
    
    conn.commit()
    conn.close()
    print("Gateway database seeded with pristine taxonomy.")

if __name__ == "__main__":
    seed_database()
