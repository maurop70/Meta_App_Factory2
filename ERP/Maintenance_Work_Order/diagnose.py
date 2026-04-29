import sqlite3, os
_here = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_here, "data", "maintenance_erp.db")
c = sqlite3.connect(DB_PATH)
c.row_factory = sqlite3.Row

print("[erp_employees table info]")
rows = c.execute("PRAGMA table_info(erp_employees)").fetchall()
for r in rows:
    print(f"  {r['name']}")

print("\n[erp_employees data (first 5)]")
rows = c.execute("SELECT id, name, authorization_level FROM erp_employees LIMIT 5").fetchall()
for r in rows:
    print(f"  ID={r['id']}  Name={r['name']}  Role={r['authorization_level']}")

print("\n[work_orders - first 3 non-COMPLETED]")
rows = c.execute("SELECT mwo_id, status, assigned_tech FROM work_orders WHERE status != 'COMPLETED' LIMIT 3").fetchall()
for r in rows:
    print(f"  MWO={r['mwo_id']}  Status={r['status']}  Tech={r['assigned_tech']}")

c.close()
