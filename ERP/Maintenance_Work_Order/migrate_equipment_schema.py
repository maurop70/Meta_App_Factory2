"""
PHASE 35.1: SCHEMA NORMALIZATION MIGRATION
============================================
Atomic table replacement for erp_equipment.
Normalizes free-text category/department columns into strictly bounded
FK-referenced lookup tables.

EXECUTION SEQUENCE:
  1. CREATE erp_categories (id TEXT PK, name TEXT UNIQUE NOT NULL)
  2. CREATE erp_departments (id TEXT PK, name TEXT UNIQUE NOT NULL)
  3. SEED lookup tables from DISTINCT values in legacy erp_equipment
  4. CREATE erp_equipment_v2 with FK constraints
  5. PORT data from erp_equipment -> erp_equipment_v2 via UUID mapping
  6. DROP TABLE erp_equipment
  7. ALTER TABLE erp_equipment_v2 RENAME TO erp_equipment

SAFETY:
  - Full pre-flight schema dump before mutation
  - Row count verification after port
  - Explicit ROLLBACK on any failure
  - Foreign keys enforced via PRAGMA

DO NOT EXECUTE WITHOUT EXPLICIT CLEARANCE.
"""

import sqlite3
import uuid
import os
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")

def generate_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def run_migration():
    print("=" * 70)
    print("PHASE 35.1: SCHEMA NORMALIZATION MIGRATION")
    print(f"TARGET DB: {DB_PATH}")
    print("=" * 70)

    if not os.path.exists(DB_PATH):
        print("FATAL: Database file does not exist.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Enable foreign key enforcement for this connection
    cursor.execute("PRAGMA foreign_keys = ON")

    # ================================================================
    # PRE-FLIGHT: Capture existing state
    # ================================================================
    print("\n--- PRE-FLIGHT STATE ---")

    cursor.execute("PRAGMA table_info(erp_equipment)")
    cols = cursor.fetchall()
    print(f"[PRE] erp_equipment columns: {[c['name'] for c in cols]}")

    cursor.execute("SELECT COUNT(*) as cnt FROM erp_equipment")
    pre_count = cursor.fetchone()['cnt']
    print(f"[PRE] erp_equipment row count: {pre_count}")

    cursor.execute("SELECT DISTINCT category FROM erp_equipment WHERE category IS NOT NULL")
    distinct_categories = [r['category'] for r in cursor.fetchall()]
    print(f"[PRE] Distinct categories: {distinct_categories}")

    cursor.execute("SELECT DISTINCT department FROM erp_equipment WHERE department IS NOT NULL")
    distinct_departments = [r['department'] for r in cursor.fetchall()]
    print(f"[PRE] Distinct departments: {distinct_departments}")

    # Check if lookup tables already exist (idempotency guard)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='erp_categories'")
    if cursor.fetchone():
        print("FATAL: erp_categories already exists. Migration may have been partially applied.")
        print("       Manual intervention required. Aborting.")
        conn.close()
        sys.exit(1)

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='erp_departments'")
    if cursor.fetchone():
        print("FATAL: erp_departments already exists. Migration may have been partially applied.")
        print("       Manual intervention required. Aborting.")
        conn.close()
        sys.exit(1)

    # ================================================================
    # MIGRATION: Atomic sequence
    # ================================================================
    print("\n--- MIGRATION EXECUTION ---")

    try:
        # Foreign keys must be OFF during table replacement (SQLite limitation).
        # We re-enable and verify after the swap.
        cursor.execute("PRAGMA foreign_keys = OFF")

        cursor.execute("BEGIN TRANSACTION")
        print("[TXN] BEGIN TRANSACTION")

        # ----------------------------------------------------------
        # STEP 1: Create lookup tables
        # ----------------------------------------------------------
        cursor.execute("""
            CREATE TABLE erp_categories (
                id   TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            )
        """)
        print("[TXN] CREATED TABLE erp_categories")

        cursor.execute("""
            CREATE TABLE erp_departments (
                id   TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            )
        """)
        print("[TXN] CREATED TABLE erp_departments")

        # ----------------------------------------------------------
        # STEP 2: Seed lookup tables from DISTINCT legacy values
        # ----------------------------------------------------------
        category_map = {}  # name -> id
        for cat_name in distinct_categories:
            cat_id = generate_id("CAT")
            cursor.execute(
                "INSERT INTO erp_categories (id, name) VALUES (?, ?)",
                (cat_id, cat_name)
            )
            category_map[cat_name] = cat_id
            print(f"[TXN] SEEDED category: '{cat_name}' -> {cat_id}")

        department_map = {}  # name -> id
        for dep_name in distinct_departments:
            dep_id = generate_id("DEP")
            cursor.execute(
                "INSERT INTO erp_departments (id, name) VALUES (?, ?)",
                (dep_id, dep_name)
            )
            department_map[dep_name] = dep_id
            print(f"[TXN] SEEDED department: '{dep_name}' -> {dep_id}")

        if not distinct_categories:
            print("[TXN] No categories to seed (table was empty)")
        if not distinct_departments:
            print("[TXN] No departments to seed (table was empty)")

        # ----------------------------------------------------------
        # STEP 3: Create normalized equipment table (v2)
        # ----------------------------------------------------------
        cursor.execute("""
            CREATE TABLE erp_equipment_v2 (
                equipment_id     TEXT PRIMARY KEY,
                nomenclature     TEXT NOT NULL,
                category_id      TEXT NOT NULL REFERENCES erp_categories(id),
                status           TEXT NOT NULL DEFAULT 'ACTIVE',
                department_id    TEXT NOT NULL REFERENCES erp_departments(id),
                assigned_tech_id TEXT REFERENCES erp_employees(id)
            )
        """)
        print("[TXN] CREATED TABLE erp_equipment_v2 (FK-normalized schema)")

        # ----------------------------------------------------------
        # STEP 4: Port data from legacy table via UUID mapping
        # ----------------------------------------------------------
        cursor.execute("""
            SELECT equipment_id, nomenclature, category, status, department, assigned_tech_id
            FROM erp_equipment
        """)
        legacy_rows = cursor.fetchall()

        ported_count = 0
        for row in legacy_rows:
            mapped_cat_id = category_map.get(row['category'])
            mapped_dep_id = department_map.get(row['department'])

            if not mapped_cat_id:
                print(f"[TXN] WARNING: Unmapped category '{row['category']}' for {row['equipment_id']}. Skipping.")
                continue
            if not mapped_dep_id:
                print(f"[TXN] WARNING: Unmapped department '{row['department']}' for {row['equipment_id']}. Skipping.")
                continue

            cursor.execute(
                """
                INSERT INTO erp_equipment_v2 
                    (equipment_id, nomenclature, category_id, status, department_id, assigned_tech_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row['equipment_id'],
                    row['nomenclature'],
                    mapped_cat_id,
                    row['status'],
                    mapped_dep_id,
                    row['assigned_tech_id']
                )
            )
            ported_count += 1

        print(f"[TXN] PORTED {ported_count}/{len(legacy_rows)} rows to erp_equipment_v2")

        # Row count verification
        if ported_count != len(legacy_rows):
            print(f"[TXN] FATAL: Row count mismatch. Expected {len(legacy_rows)}, ported {ported_count}.")
            raise RuntimeError("Data port integrity violation. Aborting.")

        # ----------------------------------------------------------
        # STEP 5: Atomic Swap
        # ----------------------------------------------------------
        cursor.execute("DROP TABLE erp_equipment")
        print("[TXN] DROPPED TABLE erp_equipment (legacy)")

        cursor.execute("ALTER TABLE erp_equipment_v2 RENAME TO erp_equipment")
        print("[TXN] RENAMED erp_equipment_v2 -> erp_equipment")

        # ----------------------------------------------------------
        # COMMIT
        # ----------------------------------------------------------
        conn.commit()
        print("[TXN] COMMIT -- migration sealed")

    except Exception as e:
        conn.rollback()
        print(f"\n[TXN] ROLLBACK -- migration failed: {e}")
        conn.close()
        sys.exit(1)

    # ================================================================
    # POST-FLIGHT: Verify new schema
    # ================================================================
    print("\n--- POST-FLIGHT VERIFICATION ---")

    # Re-enable FK enforcement for verification
    cursor.execute("PRAGMA foreign_keys = ON")

    cursor.execute("PRAGMA table_info(erp_equipment)")
    new_cols = cursor.fetchall()
    print(f"[POST] erp_equipment columns: {[c['name'] for c in new_cols]}")

    cursor.execute("SELECT COUNT(*) as cnt FROM erp_equipment")
    post_count = cursor.fetchone()['cnt']
    print(f"[POST] erp_equipment row count: {post_count}")
    assert post_count == pre_count, f"INTEGRITY FAILURE: pre={pre_count}, post={post_count}"

    cursor.execute("SELECT COUNT(*) as cnt FROM erp_categories")
    cat_count = cursor.fetchone()['cnt']
    print(f"[POST] erp_categories row count: {cat_count}")

    cursor.execute("SELECT COUNT(*) as cnt FROM erp_departments")
    dep_count = cursor.fetchone()['cnt']
    print(f"[POST] erp_departments row count: {dep_count}")

    # Verify FK integrity
    cursor.execute("PRAGMA foreign_key_check(erp_equipment)")
    fk_violations = cursor.fetchall()
    if fk_violations:
        print(f"[POST] FATAL: {len(fk_violations)} foreign key violations detected!")
        for v in fk_violations:
            print(f"       {dict(v)}")
    else:
        print("[POST] Foreign key integrity check: PASSED (0 violations)")

    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r['name'] for r in cursor.fetchall()]
    print(f"[POST] All tables: {tables}")

    conn.close()

    print(f"\n{'=' * 70}")
    print("MIGRATION COMPLETE")
    print(f"  erp_categories:  {cat_count} lookup entries")
    print(f"  erp_departments: {dep_count} lookup entries")
    print(f"  erp_equipment:   {post_count} rows (FK-normalized)")
    print(f"  Legacy columns replaced: category -> category_id, department -> department_id")
    print("=" * 70)


if __name__ == "__main__":
    run_migration()
