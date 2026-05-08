import sqlite3

conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

c.execute("UPDATE erp_procurement_queue SET status = 'APPROVED', authorized_quantity = 10 WHERE procurement_id = 'PRQ-TEST-001'")
conn.commit()
conn.close()
print("Reverted PRQ-TEST-001 to APPROVED")
