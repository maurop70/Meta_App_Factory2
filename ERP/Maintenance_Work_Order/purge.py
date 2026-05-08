import sqlite3
conn=sqlite3.connect('data/maintenance_erp.db')
conn.execute('DELETE FROM erp_parts WHERE part_id="PRT-4B32FA22"')
conn.commit()
conn.close()
print("Purged PRT-4B32FA22")
