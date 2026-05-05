import sqlite3, os
conn = sqlite3.connect(os.path.join('data', 'maintenance_erp.db'))
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("MWO-2026-102 assigned_tech:")
c.execute("SELECT mwo_id, status, assigned_tech FROM work_orders WHERE mwo_id = 'MWO-2026-102'")
print(dict(c.fetchone()))

print("\nAll IN_PROGRESS MWOs:")
c.execute("SELECT mwo_id, status, assigned_tech FROM work_orders WHERE status = 'IN_PROGRESS'")
for r in c.fetchall():
    print(f"  {dict(r)}")

print("\nAll erp_employees:")
c.execute("SELECT id, name, authorization_level FROM erp_employees")
for r in c.fetchall():
    print(f"  {dict(r)}")

# Check if any IN_PROGRESS MWO has an assigned_tech that exists in erp_employees
print("\nCross-ref: IN_PROGRESS MWOs with valid employee FK:")
c.execute("""
    SELECT w.mwo_id, w.assigned_tech, e.id as emp_id, e.name
    FROM work_orders w 
    JOIN erp_employees e ON w.assigned_tech = e.id
    WHERE w.status = 'IN_PROGRESS'
""")
matches = c.fetchall()
for m in matches:
    print(f"  {dict(m)}")
if not matches:
    print("  >>> NONE FOUND <<<")

conn.close()
