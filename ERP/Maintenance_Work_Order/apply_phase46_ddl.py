import sqlite3

sql = """
BEGIN TRANSACTION;

-- 1. ERADICATE THE ILLEGAL COLUMN (Requires SQLite 3.35.0+)
ALTER TABLE work_orders DROP COLUMN consumed_sku;

-- 2. SYNTHESIZE THE CONSUMPTION BRIDGE
CREATE TABLE IF NOT EXISTS mwo_consumed_parts (
    consumption_id TEXT PRIMARY KEY,
    mwo_id TEXT NOT NULL,
    part_id TEXT NOT NULL,
    quantity_consumed INTEGER NOT NULL CHECK (quantity_consumed > 0),
    consumed_at REAL NOT NULL,
    logged_by_tech_id TEXT NOT NULL,
    FOREIGN KEY(mwo_id) REFERENCES work_orders(mwo_id) ON DELETE RESTRICT,
    FOREIGN KEY(part_id) REFERENCES erp_parts(part_id) ON DELETE RESTRICT,
    FOREIGN KEY(logged_by_tech_id) REFERENCES erp_employees(user_id) ON DELETE RESTRICT
);

-- 3. ENFORCE INDEXING FOR QUERY OPTIMIZATION
CREATE INDEX idx_mwo_consumption ON mwo_consumed_parts(mwo_id);
CREATE INDEX idx_part_consumption ON mwo_consumed_parts(part_id);

COMMIT;
"""

try:
    conn = sqlite3.connect('data/maintenance_erp.db')
    cursor = conn.cursor()
    cursor.executescript(sql)
    print("SUCCESS: Phase 46 Consumption Bridge DDL executed and committed.")
except Exception as e:
    print(f"ERROR: {e}")
finally:
    if conn:
        conn.close()
