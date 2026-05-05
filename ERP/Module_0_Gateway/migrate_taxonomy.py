import sqlite3
import os

source_db_path = r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order\data\maintenance_erp.db"
target_db_path = r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Module_0_Gateway\data\gateway_core.db"

def migrate_taxonomy():
    if os.path.exists(target_db_path):
        os.remove(target_db_path)
        
    source_conn = sqlite3.connect(source_db_path)
    target_conn = sqlite3.connect(target_db_path)
    
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    # 1. Migrate erp_departments
    source_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='erp_departments'")
    schema = source_cursor.fetchone()[0]
    target_cursor.execute(schema)
    
    source_cursor.execute("SELECT * FROM erp_departments")
    rows = source_cursor.fetchall()
    
    if rows:
        placeholders = ",".join(["?"] * len(rows[0]))
        target_cursor.executemany(f"INSERT INTO erp_departments VALUES ({placeholders})", rows)
        
    # 2. Migrate erp_employees
    source_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='erp_employees'")
    schema = source_cursor.fetchone()[0]
    target_cursor.execute(schema)
    
    source_cursor.execute("SELECT * FROM erp_employees")
    rows = source_cursor.fetchall()
    
    if rows:
        placeholders = ",".join(["?"] * len(rows[0]))
        target_cursor.executemany(f"INSERT INTO erp_employees VALUES ({placeholders})", rows)
        
    target_conn.commit()
    source_conn.close()
    target_conn.close()
    print("Taxonomy Core Migration Complete.")

if __name__ == "__main__":
    migrate_taxonomy()
