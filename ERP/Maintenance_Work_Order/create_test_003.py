import sqlite3
import datetime

conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

# Insert PRQ-TEST-003
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
c.execute("INSERT INTO erp_procurement_queue (procurement_id, part_id, status, triggered_at, authorized_quantity) VALUES (?, ?, ?, ?, ?)", 
          ('PRQ-TEST-003', 'SKU-9902', 'APPROVED', now, 10))

conn.commit()
conn.close()
print("Inserted PRQ-TEST-003")
