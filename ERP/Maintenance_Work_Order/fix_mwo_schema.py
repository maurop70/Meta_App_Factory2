import sqlite3

sql = """
BEGIN TRANSACTION;

DROP TABLE IF EXISTS mwo_consumed_parts;

CREATE TABLE mwo_consumed_parts (
    consumption_id TEXT PRIMARY KEY,
    mwo_id TEXT NOT NULL,
    part_id TEXT NOT NULL,
    quantity_consumed INTEGER NOT NULL CHECK (quantity_consumed > 0),
    consumed_at REAL NOT NULL,
    logged_by_tech_id TEXT NOT NULL,
    FOREIGN KEY(mwo_id) REFERENCES work_orders(mwo_id) ON DELETE RESTRICT,
    FOREIGN KEY(part_id) REFERENCES erp_parts(part_id) ON DELETE RESTRICT,
    FOREIGN KEY(logged_by_tech_id) REFERENCES erp_employees(id) ON DELETE RESTRICT
);

CREATE INDEX idx_mwo_consumption ON mwo_consumed_parts(mwo_id);
CREATE INDEX idx_part_consumption ON mwo_consumed_parts(part_id);

COMMIT;
"""

try:
    conn = sqlite3.connect('data/maintenance_erp.db')
    cursor = conn.cursor()
    cursor.executescript(sql)
    print("SUCCESS: DDL correction applied.")
except Exception as e:
    print(f"ERROR: {e}")
finally:
    if conn:
        conn.close()
