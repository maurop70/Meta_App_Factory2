import sqlite3
import traceback

# DB Path
DB_PATH = "data/maintenance_erp.db"

def apply_ddl():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.cursor()
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS department_dispatch_rules (
            id TEXT PRIMARY KEY,
            department_id TEXT NOT NULL,
            assigned_hm_id TEXT NOT NULL,
            priority_tier INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES erp_departments(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_hm_id) REFERENCES erp_employees(id) ON DELETE CASCADE,
            UNIQUE(department_id, priority_tier) 
        );
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_dispatch_rules_active ON department_dispatch_rules(department_id, is_active, priority_tier);
        """)
        conn.commit()
        print("DDL applied successfully.")
    except Exception as e:
        print(f"DDL Exception: {e}")
    finally:
        conn.close()

def run_worker():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.cursor()
    try:
        print("Executing BEGIN IMMEDIATE TRANSACTION;")
        cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
        
        print("Fetching PENDING_ROUTING from work_orders...")
        # STEP 1: Fetch a single unassigned MWO and its associated department via the equipment table
        cursor.execute("""
        SELECT m.mwo_id, e.department_id 
        FROM work_orders m
        JOIN erp_equipment e ON m.equipment_id = e.equipment_id
        WHERE m.status = 'PENDING_ROUTING'
        LIMIT 1;
        """)
        row = cursor.fetchone()
        
        # IF NO ROWS RETURNED: COMMIT and sleep worker.
        if not row:
            print("No rows returned. COMMIT and sleep.")
            cursor.execute("COMMIT;")
            return

        mwo_id = row[0]
        dept_id = row[1]
        print(f"Evaluating Dispatch Matrix for department {dept_id}")
        
        # STEP 2: Evaluate the Dispatch Matrix for an active HM
        cursor.execute("""
        SELECT r.assigned_hm_id
        FROM department_dispatch_rules r
        JOIN erp_employees u ON r.assigned_hm_id = u.id
        WHERE r.department_id = ? 
          AND r.is_active = 1
          AND u.is_active = 1
        ORDER BY r.priority_tier ASC
        LIMIT 1;
        """, (dept_id,))
        hm_row = cursor.fetchone()
        
        # STEP 3: Actuate the State Mutation
        if hm_row:
            assigned_hm_id = hm_row[0]
            print(f"HM found: {assigned_hm_id}. Actuating State Mutation to DISPATCHED...")
            cursor.execute("""
            UPDATE work_orders
            SET assigned_tech = ?, status = 'DISPATCHED'
            WHERE mwo_id = ?;
            """, (assigned_hm_id, mwo_id))
        else:
            print(f"No HM found. Actuating State Mutation to UNASSIGNED_ESCALATION...")
            cursor.execute("""
            UPDATE work_orders
            SET status = 'UNASSIGNED_ESCALATION'
            WHERE mwo_id = ?;
            """, (mwo_id,))
            
        cursor.execute("COMMIT;")
        print("Worker cycle completed successfully.")
    except Exception as e:
        print(f"WORKER EXECUTION EXCEPTION:\n{traceback.format_exc()}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    apply_ddl()
    run_worker()
