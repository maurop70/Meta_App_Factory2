import sqlite3
import os

dbs = ['maintenance_erp.db', 'erp_system.db', 'local_erp.db']
for db in dbs:
    if os.path.exists(db):
        try:
            conn = sqlite3.connect(db)
            c = conn.cursor()
            c.execute("SELECT id, pin, role FROM users WHERE id='ERP-1000'")
            print(f"Found in {db}: {c.fetchall()}")
        except Exception as e:
            pass
