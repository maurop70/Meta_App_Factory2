import sqlite3
import os
from datetime import datetime, timezone

db_path = os.path.join("data", "maintenance_erp.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

def to_iso(timestamp):
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except Exception:
        return None

try:
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE TRANSACTION")
    
    # 1. Fetch existing data
    cursor.execute("SELECT * FROM work_orders")
    old_rows = cursor.fetchall()
    
    # 2. Drop the old table
    cursor.execute("DROP TABLE work_orders")
    
    # 3. Create the new hardened table
    new_ddl = """
    CREATE TABLE work_orders (
        mwo_id TEXT PRIMARY KEY,
        status TEXT NOT NULL CHECK (status IN ('UNASSIGNED', 'ASSIGNED', 'IN_PROGRESS', 'PAUSED', 'PENDING_REVIEW', 'COMPLETED', 'PENDING_ROUTING', 'DISPATCHED', 'UNASSIGNED_ESCALATION')),
        dm_urgency TEXT,
        hm_priority TEXT,
        description TEXT,
        assigned_tech TEXT REFERENCES erp_employees(id) ON DELETE RESTRICT,
        assigned_hm_id TEXT REFERENCES erp_employees(id) ON DELETE RESTRICT,
        created_by TEXT REFERENCES erp_employees(id) ON DELETE RESTRICT,
        manual_log TEXT,
        created_at TEXT,
        triaged_at TEXT,
        execution_start TEXT,
        execution_end TEXT,
        completed_at TEXT,
        start_date TEXT,
        equipment_id TEXT REFERENCES erp_equipment(equipment_id) ON DELETE RESTRICT, 
        location_id TEXT REFERENCES erp_locations(id) ON DELETE RESTRICT, 
        material_cost FLOAT, 
        archival_pdf_path TEXT, 
        resolution_notes TEXT, 
        labor_hours REAL,
        accumulated_labor_seconds REAL DEFAULT 0.0
    )
    """
    cursor.execute(new_ddl)
    
    # 4. Migrate and insert data
    for row in old_rows:
        r = dict(row)
        # Convert REAL to TEXT ISO8601
        for col in ['created_at', 'triaged_at', 'execution_start', 'execution_end']:
            if col in r and isinstance(r[col], float):
                r[col] = to_iso(r[col])
                
        # Remove consumed_sku if it existed in the query result because it was dropped in Phase 46
        if 'consumed_sku' in r:
            del r['consumed_sku']
            
        columns = ', '.join(r.keys())
        placeholders = ', '.join(['?'] * len(r))
        cursor.execute(f"INSERT INTO work_orders ({columns}) VALUES ({placeholders})", list(r.values()))
        
    conn.commit()
    print("Successfully migrated work_orders table to Phase 47 DDL schema.")

except Exception as e:
    conn.rollback()
    print(f"Migration failed: {e}")
finally:
    conn.close()
