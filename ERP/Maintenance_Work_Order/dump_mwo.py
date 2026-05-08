import sqlite3
conn=sqlite3.connect('data/maintenance_erp.db')
c=conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='work_orders'")
print(c.fetchone()[0])
