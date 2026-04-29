import sqlite3
conn = sqlite3.connect('data/maintenance_erp.db')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='work_orders';")
print(cursor.fetchone()[0])
conn.close()
