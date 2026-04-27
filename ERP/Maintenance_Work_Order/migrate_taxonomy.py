import sqlite3
import os

# DB file path (configurable)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")
TABLE_NAME = "work_orders" # Mapping user's 'mwo_table' to actual known table

def migrate_taxonomy():
    print("=" * 60)
    print("PHASE 20.64 — DESTRUCTIVE SCHEMA MIGRATION: 5-PHASE TAXONOMY")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Begin Transaction
        cursor.execute("BEGIN TRANSACTION;")

        # 2. Extract current records
        print("[*] Extracting current records...")
        cursor.execute(f"SELECT * FROM {TABLE_NAME}")
        rows = cursor.fetchall()
        
        reconciled_data = []
        for row in rows:
            record = dict(row)
            
            tech = record.get('assigned_tech')
            current_status = record.get('status')
            
            # Logic A: Nullify fake strings
            if not tech or str(tech).strip() == "" or str(tech).strip().upper() == "UNASSIGNED":
                record['assigned_tech'] = None
                record['status'] = 'UNASSIGNED'
            
            # Logic B: Only remap legacy 'OPEN' (or weird triage states) to 'ASSIGNED'
            elif tech and current_status == 'OPEN':
                record['status'] = 'ASSIGNED'
                
            # Note: PENDING_REVIEW remains PENDING_REVIEW if tech is assigned. 
            # IN_PROGRESS remains IN_PROGRESS. COMPLETED remains COMPLETED.
                
            reconciled_data.append(record)

        print(f"[*] Reconciled {len(reconciled_data)} records.")

        # 3. Create mwo_table_new with CHECK constraint
        print("[*] Creating new schema with strict CHECK constraint...")
        create_new_table_sql = """
        CREATE TABLE work_orders_new (
            mwo_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('UNASSIGNED', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_REVIEW', 'COMPLETED')),
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
            equipment_id TEXT
        );
        """
        cursor.execute(create_new_table_sql)

        # 4. Insert reconciled data
        if reconciled_data:
            # Force exact schema column mapping
            schema_columns = [
                'mwo_id', 'status', 'dm_urgency', 'hm_priority', 'description', 
                'assigned_tech', 'consumed_sku', 'manual_log', 'created_at', 
                'triaged_at', 'execution_start', 'execution_end', 'completed_at', 
                'start_date', 'equipment_id'
            ]
            placeholders = ", ".join(["?" for _ in schema_columns])
            insert_sql = f"INSERT INTO work_orders_new ({', '.join(schema_columns)}) VALUES ({placeholders})"
            
            for data_dict in reconciled_data:
                # Use .get() to prevent KeyErrors if legacy DB lacks a column
                values = [data_dict.get(col, None) for col in schema_columns]
                cursor.execute(insert_sql, values)
        
        print(f"[*] Inserted {len(reconciled_data)} reconciled records into new table.")

        # 5. Drop old table and rename new table
        print("[*] Dropping legacy table...")
        cursor.execute(f"DROP TABLE {TABLE_NAME};")
        
        print("[*] Renaming new table to primary table...")
        cursor.execute(f"ALTER TABLE work_orders_new RENAME TO {TABLE_NAME};")

        # 6. Commit Transaction
        conn.commit()
        print("[SUCCESS] Schema migration and taxonomy enforcement completed.")

    except Exception as e:
        conn.rollback()
        print(f"[FATAL] Migration failed. Transaction rolled back. Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_taxonomy()
