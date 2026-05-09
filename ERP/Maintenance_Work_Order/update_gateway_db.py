import sqlite3

db_path = "/opt/erp/gateway/data/gateway_core.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("UPDATE erp_employees SET role='ADMINISTRATOR', pin='1234', status='ACTIVE' WHERE emp_id='ERP-1000'")
conn.commit()

c.execute("SELECT emp_id, role, pin, status FROM erp_employees WHERE emp_id='ERP-1000'")
print("Updated gateway:", c.fetchone())

conn.close()
