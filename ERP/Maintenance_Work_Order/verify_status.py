import sqlite3
db_path = "data/maintenance_erp.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT mwo_id, status, start_date, equipment_id, completion_date FROM work_orders ORDER BY mwo_id")
rows = cursor.fetchall()
for r in rows:
    print(f"  {r['mwo_id']} | STATUS={r['status']} | start={r['start_date']} | eq={r['equipment_id']} | completed={r['completion_date']}")
conn.close()
