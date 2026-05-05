import sqlite3
import os
import uuid
import bcrypt

def execute_migration():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Pre-flight: Lock out foreign keys to allow table swapping
    c.execute("PRAGMA foreign_keys = OFF")
    
    # ---------------------------------------------------------
    # 1. Fetch and Pre-Compute (OUTSIDE TRANSACTION)
    # ---------------------------------------------------------
    c.execute("SELECT * FROM erp_employees")
    legacy_employees = [dict(row) for row in c.fetchall()]
    
    # Pre-compute bcrypt hashes in memory to prevent CPU-bound lock escalation
    for emp in legacy_employees:
        if not emp['pin_hash']:
            raw_pin = str(emp['pin_code'])
            emp['pin_hash'] = bcrypt.hashpw(raw_pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # ---------------------------------------------------------
    # 2. Execute Atomic I/O (INSIDE TRANSACTION)
    # ---------------------------------------------------------
    c.execute("BEGIN TRANSACTION")
    try:
        # Ledger Rebuild
        c.execute("""
            CREATE TABLE erp_employees_v2 (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('ADMINISTRATOR', 'ADMIN', 'HM', 'TECH')),
                pin_hash TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                department_id TEXT REFERENCES erp_departments(id),
                reports_to_hm_id TEXT REFERENCES erp_employees_v2(id)
            )
        """)
        
        # Build department lookup map
        c.execute("SELECT name, id FROM erp_departments")
        dept_map = {row['name']: row['id'] for row in c.fetchall()}
        
        # Data Porting & Binding
        for emp in legacy_employees:
            # Map Role (Parity Mismatch Resolution)
            legacy_role = emp['authorization_level']
            new_role = 'TECH' if legacy_role == 'TECHNICIAN' else legacy_role
            
            # Map Department to FK
            legacy_dept_name = emp['department']
            dept_id = None
            if legacy_dept_name:
                if legacy_dept_name in dept_map:
                    dept_id = dept_map[legacy_dept_name]
                else:
                    # Synthesize missing department to maintain physical domain integrity
                    new_dept_id = f"DEP-{uuid.uuid4().hex[:6].upper()}"
                    c.execute("INSERT INTO erp_departments (id, name) VALUES (?, ?)", (new_dept_id, legacy_dept_name))
                    dept_map[legacy_dept_name] = new_dept_id
                    dept_id = new_dept_id

            # Insert into normalized ledger (using pre-computed pin_hash)
            c.execute("""
                INSERT INTO erp_employees_v2 
                (id, name, role, pin_hash, is_active, department_id, reports_to_hm_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                emp['id'],
                emp['name'],
                new_role,
                emp['pin_hash'],
                emp['is_active'],
                dept_id,
                emp['reports_to_hm_id']
            ))
            
        # Atomic Swap
        c.execute("DROP TABLE erp_employees")
        c.execute("ALTER TABLE erp_employees_v2 RENAME TO erp_employees")
        
        # ---------------------------------------------------------
        # 3. Pre-Commit Integrity Guard
        # ---------------------------------------------------------
        c.execute("PRAGMA foreign_key_check(erp_employees)")
        fk_violations = c.fetchall()
        if fk_violations:
            raise sqlite3.IntegrityError(f"Relational binding failure detected prior to commit: {fk_violations}")
        
        # Physically seal the transaction only if integrity checks pass
        conn.commit()
        print("[SUCCESS] Phase 35.3 Migration complete. Database structurally normalized.")
        
    except Exception as e:
        conn.rollback()
        print(f"[FATAL] Migration failed. Transaction rolled back. Error: {e}")
        raise
    finally:
        # Re-enable pragmas
        c.execute("PRAGMA foreign_keys = ON")
        conn.close()

if __name__ == "__main__":
    execute_migration()
