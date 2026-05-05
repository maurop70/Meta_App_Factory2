import sqlite3
DB_PATH = "C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
try:
    cursor.execute("INSERT INTO erp_employees (id, name, role, pin_hash, is_active, department_id) VALUES ('ERP-2000', 'HM Persona', 'HM', 'mockhash', 1, 'TEST-DEPT')")
    cursor.execute("INSERT INTO erp_employees (id, name, role, pin_hash, is_active, department_id) VALUES ('ERP-3000', 'Tech Persona', 'TECH', 'mockhash', 1, 'TEST-DEPT')")
    conn.commit()
    print("Inserted")
except Exception as e:
    print(f"Error: {e}")
