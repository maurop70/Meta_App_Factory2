"""
Phase 34.9: MWO State Interrogation
Outputs the full state of every MWO in the ledger to identify valid active targets.
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 80)
print("MWO LEDGER STATE INTERROGATION")
print(f"DB PATH: {DB_PATH}")
print("=" * 80)

# 1. Full MWO State Dump
print("\n[1] SELECT mwo_id, status, assigned_tech, equipment_id FROM work_orders ORDER BY mwo_id;\n")
cursor.execute("SELECT mwo_id, status, assigned_tech, equipment_id FROM work_orders ORDER BY mwo_id")
rows = cursor.fetchall()
if not rows:
    print("    >>> NO WORK ORDERS FOUND IN LEDGER <<<")
else:
    print(f"    {'MWO_ID':<25} {'STATUS':<15} {'ASSIGNED_TECH':<20} {'EQUIPMENT_ID':<20}")
    print(f"    {'-'*25} {'-'*15} {'-'*20} {'-'*20}")
    for r in rows:
        print(f"    {r['mwo_id']:<25} {r['status']:<15} {str(r['assigned_tech'] or 'NULL'):<20} {str(r['equipment_id'] or 'NULL'):<20}")

print(f"\n    Total MWOs: {len(rows)}")

# 2. Classify
completed = [r for r in rows if r['status'] == 'COMPLETED']
active = [r for r in rows if r['status'] in ('IN_PROGRESS', 'ASSIGNED', 'OPEN')]
unassigned = [r for r in rows if r['status'] == 'UNASSIGNED']
other = [r for r in rows if r['status'] not in ('COMPLETED', 'IN_PROGRESS', 'ASSIGNED', 'OPEN', 'UNASSIGNED')]

print(f"\n[2] STATE CLASSIFICATION:")
print(f"    COMPLETED:   {len(completed)} — {[r['mwo_id'] for r in completed]}")
print(f"    ACTIVE:      {len(active)} — {[r['mwo_id'] for r in active]}")
print(f"    UNASSIGNED:  {len(unassigned)} — {[r['mwo_id'] for r in unassigned]}")
print(f"    OTHER:       {len(other)} — {[(r['mwo_id'], r['status']) for r in other]}")

# 3. Inventory snapshot
print(f"\n[3] SELECT part_id, nomenclature, quantity_on_hand FROM erp_parts;\n")
cursor.execute("SELECT part_id, nomenclature, quantity_on_hand FROM erp_parts ORDER BY part_id")
parts = cursor.fetchall()
for p in parts:
    print(f"    {p['part_id']:<15} {p['nomenclature']:<30} qty={p['quantity_on_hand']}")

# 4. Existing ledger entries
print(f"\n[4] SELECT * FROM erp_inventory_ledger ORDER BY transaction_timestamp DESC LIMIT 10;\n")
cursor.execute("SELECT transaction_id, part_id, mwo_id, tech_id, quantity_consumed, transaction_timestamp FROM erp_inventory_ledger ORDER BY transaction_timestamp DESC LIMIT 10")
ledger = cursor.fetchall()
if not ledger:
    print("    >>> LEDGER IS EMPTY <<<")
else:
    for l in ledger:
        print(f"    {l['transaction_id']} | {l['part_id']} | {l['mwo_id']} | tech={l['tech_id']} | qty={l['quantity_consumed']} | {l['transaction_timestamp']}")

conn.close()
print(f"\n{'=' * 80}")
print("INTERROGATION COMPLETE")
print("=" * 80)
