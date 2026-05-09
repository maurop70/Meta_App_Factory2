import sqlite3

db_path = "/opt/erp/backend/data/maintenance_erp.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT * FROM erp_employees WHERE id='ERP-1000'")
row = c.fetchone()
print("ERP-1000 row:", row)
conn.close()
