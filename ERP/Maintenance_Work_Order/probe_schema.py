import sqlite3, os

conn = sqlite3.connect(os.path.join('data', 'maintenance_erp.db'))
c = conn.cursor()

print("=" * 60)
print("SCHEMA AUDIT: AY PROPOSAL CROSS-REFERENCE")
print("=" * 60)

# 1. List all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in c.fetchall()]
print(f"\n[1] ALL TABLES ({len(tables)}):")
for t in tables:
    print(f"    {t}")

# 2. Check for AY's proposed tables
print("\n[2] AY PROPOSED TABLE EXISTENCE:")
for t in ['erp_categories', 'erp_departments', 'personnel']:
    exists = t in tables
    print(f"    {t}: {'EXISTS' if exists else '>>> DOES NOT EXIST <<<'}")

# 3. Show erp_equipment schema
print("\n[3] erp_equipment SCHEMA:")
c.execute("PRAGMA table_info(erp_equipment)")
for col in c.fetchall():
    print(f"    {col}")

# 4. Show erp_employees schema  
print("\n[4] erp_employees SCHEMA:")
c.execute("PRAGMA table_info(erp_employees)")
for col in c.fetchall():
    print(f"    {col}")

# 5. Sample erp_equipment data
print("\n[5] erp_equipment SAMPLE (5 rows):")
c.execute("SELECT * FROM erp_equipment LIMIT 5")
rows = c.fetchall()
if rows:
    cols = [d[0] for d in c.description]
    print(f"    COLUMNS: {cols}")
    for r in rows:
        print(f"    {dict(zip(cols, r))}")
else:
    print("    >>> TABLE IS EMPTY <<<")

# 6. Distinct categories in equipment
print("\n[6] DISTINCT category VALUES in erp_equipment:")
c.execute("SELECT DISTINCT category FROM erp_equipment")
for r in c.fetchall():
    print(f"    {r[0]}")

# 7. Distinct departments
print("\n[7] DISTINCT department VALUES in erp_equipment:")
c.execute("SELECT DISTINCT department FROM erp_equipment")
for r in c.fetchall():
    print(f"    {r[0]}")

conn.close()
print("\n" + "=" * 60)
