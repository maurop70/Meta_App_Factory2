import sqlite3
import json

db_path = 'C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT mwo_id, status, assigned_hm_id, execution_start, archival_pdf_path FROM work_orders")
rows = [dict(row) for row in cursor.fetchall()]

with open('db_dump.json', 'w') as f:
    json.dump(rows, f, indent=2)
