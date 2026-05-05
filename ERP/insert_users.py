import sqlite3
import os

DB_PATH = "C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("INSERT INTO erp_employees (id, name, role, is_active, department_id) VALUES ('ERP-2000', 'HM Persona', 'HM', 1, 'TEST-DEPT')")
except sqlite3.IntegrityError:
    cursor.execute("UPDATE erp_employees SET department_id = 'TEST-DEPT' WHERE id = 'ERP-2000'")

try:
    cursor.execute("INSERT INTO erp_employees (id, name, role, is_active, department_id) VALUES ('ERP-3000', 'Tech Persona', 'TECH', 1, 'TEST-DEPT')")
except sqlite3.IntegrityError:
    cursor.execute("UPDATE erp_employees SET department_id = 'TEST-DEPT' WHERE id = 'ERP-3000'")

cursor.execute("UPDATE erp_employees SET department_id = 'TEST-DEPT' WHERE id = 'ERP-1000'")
cursor.execute("UPDATE erp_equipment SET department_id = 'TEST-DEPT', assigned_hm_id = 'ERP-2000' WHERE equipment_id = (SELECT equipment_id FROM erp_equipment LIMIT 1)")

conn.commit()

cursor.execute("SELECT * FROM erp_employees WHERE id IN ('ERP-1000', 'ERP-2000', 'ERP-3000')")
for row in cursor.fetchall():
    print(row)

cursor.execute("SELECT equipment_id, department_id, assigned_hm_id FROM erp_equipment WHERE department_id = 'TEST-DEPT'")
print("Equip:", cursor.fetchone())
