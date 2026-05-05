import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'maintenance_erp.db')

def migrate():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE TRANSACTION")
    try:
        # Create new table
        cursor.execute("""
        CREATE TABLE work_orders_new (
            mwo_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('UNASSIGNED', 'ASSIGNED', 'IN_PROGRESS', 'PAUSED', 'PENDING_REVIEW', 'COMPLETED', 'PENDING_ROUTING', 'DISPATCHED', 'UNASSIGNED_ESCALATION')),
            dm_urgency TEXT,
            hm_priority TEXT,
            description TEXT,
            assigned_tech TEXT,
            consumed_sku TEXT,
            manual_log TEXT,
            created_at REAL,
            triaged_at REAL,
            execution_start REAL,
            execution_end REAL,
            completed_at TEXT,
            start_date TEXT,
            equipment_id TEXT, 
            location_id TEXT, 
            material_cost FLOAT, 
            archival_pdf_path TEXT, 
            resolution_notes TEXT, 
            labor_hours REAL,
            accumulated_labor_seconds REAL DEFAULT 0.0
        )
        """)

        # Copy data
        cursor.execute("""
        INSERT INTO work_orders_new (
            mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, 
            consumed_sku, manual_log, created_at, triaged_at, execution_start, 
            execution_end, completed_at, start_date, equipment_id, location_id, 
            material_cost, archival_pdf_path, resolution_notes, labor_hours, accumulated_labor_seconds
        )
        SELECT 
            mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, 
            consumed_sku, manual_log, created_at, triaged_at, execution_start, 
            execution_end, completed_at, start_date, equipment_id, location_id, 
            material_cost, archival_pdf_path, resolution_notes, labor_hours, 0.0
        FROM work_orders
        """)

        # Drop old and rename
        cursor.execute("DROP TABLE work_orders")
        cursor.execute("ALTER TABLE work_orders_new RENAME TO work_orders")

        conn.commit()
        print("Migration successful: added accumulated_labor_seconds and PAUSED constraint.")
    except Exception as e:
        conn.rollback()
        print("Migration failed:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
