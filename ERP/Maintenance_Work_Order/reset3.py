import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")
with sqlite3.connect(db_path) as conn:
    conn.execute("UPDATE work_orders SET status='ASSIGNED';")
    conn.commit()
print("Reset successful!")
