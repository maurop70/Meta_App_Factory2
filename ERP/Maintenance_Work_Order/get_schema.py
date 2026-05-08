import sqlite3
import pprint

conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='mwo_consumed_parts';")
res = c.fetchone()
if res:
    print(res[0])
else:
    print("Table not found")

c.execute("SELECT * FROM erp_parts LIMIT 5;")
print("\nParts:")
for row in c.fetchall():
    print(row)

c.execute("SELECT * FROM erp_employees LIMIT 5;")
print("\nEmployees:")
for row in c.fetchall():
    print(row)
    
conn.close()
