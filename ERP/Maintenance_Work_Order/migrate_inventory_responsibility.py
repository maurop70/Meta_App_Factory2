"""
Idempotent migration: Departmental Inventory Responsibility Routing.

Adds the columns that back the "Inventory Manager" model and binds the
existing seed categories to their departments:

  * erp_employees.is_inventory_manager  (ERP ledger + Gateway IAM copy)
  * erp_categories.department_id         (ERP ledger)

Run from anywhere; paths are resolved relative to this file.
"""
import sqlite3
import os


def run():
    # 1. Update ERP Database (the live ledger lives under Maintenance_Work_Order/data)
    erp_db = os.path.join(os.path.dirname(__file__), "data", "maintenance_erp.db")
    conn = sqlite3.connect(erp_db)
    try:
        cursor = conn.cursor()

        # Add is_inventory_manager to erp_employees
        cursor.execute("PRAGMA table_info(erp_employees)")
        columns = {row[1] for row in cursor.fetchall()}
        if "is_inventory_manager" not in columns:
            cursor.execute("ALTER TABLE erp_employees ADD COLUMN is_inventory_manager INTEGER DEFAULT 0")
            print("Added erp_employees.is_inventory_manager")

        # Add department_id to erp_categories
        cursor.execute("PRAGMA table_info(erp_categories)")
        cat_columns = {row[1] for row in cursor.fetchall()}
        if "department_id" not in cat_columns:
            cursor.execute("ALTER TABLE erp_categories ADD COLUMN department_id TEXT REFERENCES erp_departments(id)")
            print("Added erp_categories.department_id")

        # Bind existing seed categories to their departments (idempotent: only
        # sets the link when a matching category/department pair is present).
        cursor.execute("UPDATE erp_categories SET department_id = 'DEPT-MECH' WHERE id = 'CAT-MAINT'")
        cursor.execute("UPDATE erp_categories SET department_id = 'DEPT-ELEC' WHERE id = 'CAT-SENSORS'")

        conn.commit()
        print(f"ERP ledger migrated: {erp_db}")
    finally:
        conn.close()

    # 2. Update Gateway Database (IAM copy of erp_employees). The gateway lives
    # under "Module_0_Gateway" in the source tree but is deployed as "gateway"
    # on the droplet (the deploy transforms the dir name), so probe both layouts.
    here = os.path.dirname(__file__)
    gateway_candidates = [
        os.path.join(here, "..", "Module_0_Gateway", "data", "gateway_core.db"),
        os.path.join(here, "..", "gateway", "data", "gateway_core.db"),
    ]
    gateway_db = next((p for p in gateway_candidates if os.path.exists(p)), None)
    if gateway_db:
        conn = sqlite3.connect(gateway_db)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(erp_employees)")
            columns = {row[1] for row in cursor.fetchall()}
            if "is_inventory_manager" not in columns:
                cursor.execute("ALTER TABLE erp_employees ADD COLUMN is_inventory_manager INTEGER DEFAULT 0")
                print("Added gateway erp_employees.is_inventory_manager")
            conn.commit()
            print(f"Gateway IAM migrated: {gateway_db}")
        finally:
            conn.close()
    else:
        print(f"[WARN] Gateway DB not found in {gateway_candidates}; skipped IAM column.")


if __name__ == "__main__":
    run()
