import sqlite3, os

_here = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_here, "data", "maintenance_erp.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 70)
print("PHASE 34.9: PHYSICAL SCHEMA VERIFICATION")
print("=" * 70)

# Verify erp_parts table
print("\n[TABLE] erp_parts")
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='erp_parts'")
row = cursor.fetchone()
print(row[0] if row else "TABLE NOT FOUND")

# Verify erp_inventory_ledger table
print("\n[TABLE] erp_inventory_ledger")
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='erp_inventory_ledger'")
row = cursor.fetchone()
print(row[0] if row else "TABLE NOT FOUND")

# Verify indexes
print("\n[INDEXES]")
cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND tbl_name IN ('erp_parts', 'erp_inventory_ledger')")
for idx in cursor.fetchall():
    print(f"  {idx[0]} ON {idx[1]}: {idx[2]}")

# Verify column enumeration
print("\n[COLUMN ENUMERATION] erp_parts")
cursor.execute("PRAGMA table_info(erp_parts)")
for col in cursor.fetchall():
    print(f"  {col[1]:25s} | {col[2]:10s} | NOT_NULL={col[3]} | DEFAULT={col[4]}")

print("\n[COLUMN ENUMERATION] erp_inventory_ledger")
cursor.execute("PRAGMA table_info(erp_inventory_ledger)")
for col in cursor.fetchall():
    print(f"  {col[1]:25s} | {col[2]:10s} | NOT_NULL={col[3]} | DEFAULT={col[4]}")

print("\n" + "=" * 70)
print("SCHEMA VERIFICATION COMPLETE")
print("=" * 70)

conn.close()
