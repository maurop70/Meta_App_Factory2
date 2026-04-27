import sqlite3
conn = sqlite3.connect(r'C:\erp_local_data\maintenance_erp.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM work_orders WHERE mwo_id = ''")
conn.commit()
print("Deleted rows:", cursor.rowcount)
conn.close()
