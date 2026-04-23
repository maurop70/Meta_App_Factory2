import sqlite3
import os
import time
import shutil

def migrate():
    db_dir = r"C:\erp_local_data"
    db_path = os.path.join(db_dir, "maintenance_erp.db")
    backup_path = os.path.join(db_dir, "maintenance_erp_v1_backup.db")
    
    print(f"Checking database directory: {db_dir}")
    os.makedirs(db_dir, exist_ok=True)
    
    # Pre-Flight Guard: Backup DB if it exists (Guarded SQL drop)
    if os.path.exists(db_path):
        print(f"[GUARD] Creating backup of existing database to {backup_path}")
        shutil.copy2(db_path, backup_path)
    
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Executing DROP TABLE IF EXISTS work_orders (V1 Schema Annihilation)...")
    cursor.execute("DROP TABLE IF EXISTS work_orders;")
    
    print("Executing CREATE TABLE work_orders (V2 Schema)...")
    create_table_sql = """
    CREATE TABLE work_orders (
        mwo_id TEXT PRIMARY KEY,
        status TEXT,
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
        completed_at REAL
    );
    """
    cursor.execute(create_table_sql)
    
    print("Seeding new table with 3 synthetic records...")
    current_time = time.time()
    seed_data = [
        ("MWO-2026-001", "AWAITING_TRIAGE", "HIGH", "CRITICAL", "Line 4 conveyer motor fault", "UNASSIGNED", "", "", current_time, None, None, None, None),
        ("MWO-2026-002", "ASSIGNED", "MEDIUM", "HIGH", "Ammonia leak in chiller 2", "Tech-Alpha", "", "", current_time - 3600, current_time - 1800, None, None, None),
        ("MWO-2026-003", "IN_PROGRESS", "LOW", "MEDIUM", "Routine grease application bearing 7", "Tech-Bravo", "SKU-GRZ-001", "Applied 50g grease", current_time - 86400, current_time - 80000, current_time - 3600, None, None)
    ]
    
    insert_sql = """
    INSERT INTO work_orders (
        mwo_id, status, dm_urgency, hm_priority, description, assigned_tech, 
        consumed_sku, manual_log, created_at, triaged_at, execution_start, execution_end, completed_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    cursor.executemany(insert_sql, seed_data)
    conn.commit()
    
    print("Verifying seeding...")
    cursor.execute("SELECT mwo_id, status FROM work_orders;")
    rows = cursor.fetchall()
    for row in rows:
        print(f"  -> {row[0]}: {row[1]}")
        
    conn.close()
    print("Migration Step 1 Complete.")

if __name__ == "__main__":
    migrate()
