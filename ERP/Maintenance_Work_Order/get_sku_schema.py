import sqlite3

conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='erp_skus';")
print(c.fetchone()[0])
conn.close()
