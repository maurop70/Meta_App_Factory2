import sqlite3
import datetime

conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

# Get a part_id to use
c.execute("SELECT part_id FROM erp_parts LIMIT 1")
part = c.fetchone()
if part:
    part_id = part[0]
    now = datetime.datetime.utcnow().isoformat() + "Z"
    c.execute("INSERT INTO erp_procurement_queue (procurement_id, part_id, status, triggered_at) VALUES (?, ?, ?, ?)",
              ('PRQ-TEST-001', part_id, 'PENDING', now))
    conn.commit()
    print(f"Inserted PRQ-TEST-001 for part {part_id}")
else:
    print("No parts found to insert procurement.")
conn.close()
