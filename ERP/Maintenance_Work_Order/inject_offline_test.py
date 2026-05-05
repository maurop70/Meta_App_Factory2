import sqlite3
import os
import time

db_path = os.path.join(os.path.dirname(__file__), 'data', 'maintenance_erp.db')

def inject():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Target Identity
    user_id = 'ERP-1000'
    
    # Payloads
    payloads = [
        ('MWO-OFFLINE-01', 'ASSIGNED', 'EQ-TEST-1', 'Test offline completion lockouts.', user_id, time.time() - 86400),
        ('MWO-OFFLINE-02', 'ASSIGNED', 'EQ-TEST-2', 'Test offline pause states.', user_id, time.time() - 40000),
        ('MWO-OFFLINE-03', 'PAUSED', 'EQ-TEST-3', 'Test resumption from paused state.', user_id, time.time() - 10000)
    ]
    
    try:
        for mwo_id, status, equip, desc, tech, created in payloads:
            cursor.execute("""
                INSERT OR IGNORE INTO work_orders (mwo_id, status, equipment_id, description, assigned_tech, created_at, dm_urgency, hm_priority)
                VALUES (?, ?, ?, ?, ?, ?, 'Normal', 'Normal')
            """, (mwo_id, status, equip, desc, tech, created))
            
            # If it already exists, forcefully update it to ensure clean test state
            cursor.execute("""
                UPDATE work_orders 
                SET status = ?, assigned_tech = ?, execution_start = NULL, accumulated_labor_seconds = 0.0
                WHERE mwo_id = ?
            """, (status, tech, mwo_id))
            
        conn.commit()
        print("Test payload injected successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Injection Failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    inject()
