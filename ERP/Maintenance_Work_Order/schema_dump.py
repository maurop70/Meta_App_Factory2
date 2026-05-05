import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'maintenance_erp.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='work_orders'")
print(cursor.fetchone()[0])
conn.close()
