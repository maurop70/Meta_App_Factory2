import sqlite3, os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 80)
print("TARGET MWO STATE REPORT")
print("=" * 80)

# Count by status
c.execute("SELECT status, COUNT(*) as cnt FROM work_orders GROUP BY status ORDER BY status")
print("\n[A] STATUS DISTRIBUTION:")
for r in c.fetchall():
    print(f"    {r['status']:<20} {r['cnt']}")

# Active candidates
print("\n[B] ACTIVE TARGETS (IN_PROGRESS / ASSIGNED / OPEN):")
c.execute("SELECT mwo_id, status, assigned_tech, equipment_id FROM work_orders WHERE status IN ('IN_PROGRESS','ASSIGNED','OPEN') ORDER BY mwo_id")
active = c.fetchall()
if not active:
    print("    >>> NO ACTIVE MWOs EXIST <<<")
else:
    for r in active:
        print(f"    {r['mwo_id']:<25} {r['status']:<15} tech={r['assigned_tech'] or 'NULL':<15} equip={r['equipment_id'] or 'NULL'}")

# MWO-VERIFY-001 specifically
print("\n[C] TARGET MWO-VERIFY-001 STATE:")
c.execute("SELECT mwo_id, status, assigned_tech, equipment_id FROM work_orders WHERE mwo_id = 'MWO-VERIFY-001'")
target = c.fetchone()
if target:
    print(f"    mwo_id:        {target['mwo_id']}")
    print(f"    status:        {target['status']}")
    print(f"    assigned_tech: {target['assigned_tech'] or 'NULL'}")
    print(f"    equipment_id:  {target['equipment_id'] or 'NULL'}")
else:
    print("    >>> MWO-VERIFY-001 NOT FOUND <<<")

# UNASSIGNED candidates
print("\n[D] UNASSIGNED MWOs (first 10):")
c.execute("SELECT mwo_id, status, assigned_tech FROM work_orders WHERE status = 'UNASSIGNED' LIMIT 10")
for r in c.fetchall():
    print(f"    {r['mwo_id']:<25} {r['status']:<15} tech={r['assigned_tech'] or 'NULL'}")

conn.close()
print("\n" + "=" * 80)
