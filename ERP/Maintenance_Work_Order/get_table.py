import sqlite3
c=sqlite3.connect('data/maintenance_erp.db').cursor()
c.execute("SELECT sql FROM sqlite_master WHERE name='erp_procurement_queue'")
res = c.fetchone()
print(res[0] if res else "No table found")
