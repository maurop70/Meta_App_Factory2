import sqlite3
import os

db_path = os.path.join('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order', 'data', 'maintenance_erp.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("BEGIN TRANSACTION")
    
    tables = [
        "work_orders", "department_dispatch_rules", "procurement_events",
        "erp_equipment", "erp_parts", "erp_locations", "erp_departments", "erp_categories"
    ]
    
    for table in tables:
        try:
            c.execute(f"DELETE FROM {table}")
        except Exception as e:
            pass
            
    # Delete non-ADMIN employees
    c.execute("DELETE FROM erp_employees WHERE role NOT IN ('ADMIN', 'ADMINISTRATOR')")
    
    conn.commit()
    print("Database wiped successfully. Real data ready for ingestion.")
except Exception as e:
    conn.rollback()
    print(f"Wipe failed: {e}")
finally:
    conn.close()
