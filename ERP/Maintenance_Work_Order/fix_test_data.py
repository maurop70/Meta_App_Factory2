import sqlite3

conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

c.execute("UPDATE erp_procurement_queue SET part_id = 'PRT-670FC7CA' WHERE procurement_id = 'PRQ-TEST-001'")
conn.commit()
conn.close()
print('Reverted PRQ-TEST-001 part_id')
