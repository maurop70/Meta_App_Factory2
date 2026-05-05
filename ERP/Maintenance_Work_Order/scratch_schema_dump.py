import sqlite3
import os

db_path = os.path.join("data", "maintenance_erp.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(erp_employees)")
rows = cursor.fetchall()

print(f"{'CID':<5} | {'NAME':<20} | {'TYPE':<15} | {'NOTNULL':<7} | {'DFLT_VALUE':<10} | PK")
print("-" * 75)
for r in rows:
    print(f"{r['cid']:<5} | {r['name']:<20} | {r['type']:<15} | {r['notnull']:<7} | {str(r['dflt_value']):<10} | {r['pk']}")

conn.close()
