import sqlite3

db_path = "data/maintenance_erp.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Pre-backfill state
cursor.execute("SELECT mwo_id, status, start_date, equipment_id FROM work_orders WHERE mwo_id = 'MWO-2026-002'")
row = cursor.fetchone()
if row:
    print(f"[PRE-BACKFILL]  mwo_id={row['mwo_id']} | status={row['status']} | start_date={row['start_date']} | equipment_id={row['equipment_id']}")
else:
    print("[PRE-BACKFILL]  MWO-2026-002 NOT FOUND in work_orders")

# Atomic backfill
conn.execute("UPDATE work_orders SET start_date = '2026-04-26T00:00:00Z', equipment_id = 'EQ-CHILLER-02' WHERE mwo_id = 'MWO-2026-002'")
conn.commit()

# Post-backfill verification
cursor.execute("SELECT mwo_id, status, start_date, equipment_id FROM work_orders WHERE mwo_id = 'MWO-2026-002'")
row = cursor.fetchone()
if row:
    print(f"[POST-BACKFILL] mwo_id={row['mwo_id']} | status={row['status']} | start_date={row['start_date']} | equipment_id={row['equipment_id']}")

conn.close()
print("[COMMIT] Transaction committed. DB closed cleanly.")
