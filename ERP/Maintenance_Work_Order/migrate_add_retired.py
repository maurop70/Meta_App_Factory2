import sqlite3, os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("PRAGMA foreign_keys = OFF")
c.execute("BEGIN TRANSACTION")

c.execute("""
    CREATE TABLE erp_equipment_v3 (
        equipment_id TEXT PRIMARY KEY,
        nomenclature TEXT NOT NULL,
        category_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('ACTIVE','DEGRADED','OFFLINE','RETIRED')),
        department_id TEXT NOT NULL,
        assigned_tech_id TEXT,
        FOREIGN KEY(category_id) REFERENCES erp_categories(id),
        FOREIGN KEY(department_id) REFERENCES erp_departments(id),
        FOREIGN KEY(assigned_tech_id) REFERENCES erp_employees(id)
    )
""")

c.execute("INSERT INTO erp_equipment_v3 SELECT * FROM erp_equipment")
c.execute("DROP TABLE erp_equipment")
c.execute("ALTER TABLE erp_equipment_v3 RENAME TO erp_equipment")
c.execute("CREATE INDEX IF NOT EXISTS idx_equipment_dept_status ON erp_equipment(department_id, status)")

conn.commit()
print("CHECK constraint updated: RETIRED state added to status enum")

# Verify
c.execute("SELECT sql FROM sqlite_master WHERE name='erp_equipment'")
print(c.fetchone()[0])
conn.close()
