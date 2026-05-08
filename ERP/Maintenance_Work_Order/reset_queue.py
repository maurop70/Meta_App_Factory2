import sqlite3
import datetime

conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

# Delete existing
c.execute("DELETE FROM erp_procurement_queue WHERE procurement_id LIKE 'PRQ-TEST-%'")

# Insert PRQ-TEST-005 with CORRECT part_id
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
c.execute("INSERT INTO erp_procurement_queue (procurement_id, part_id, status, triggered_at, authorized_quantity) VALUES (?, ?, ?, ?, ?)", 
          ('PRQ-TEST-005', 'PRT-670FC7CA', 'APPROVED', now, 10))

conn.commit()
conn.close()
print("Cleaned up and inserted PRQ-TEST-005 correctly")
