import sqlite3
import os
import uuid

def execute_migration():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Pre-flight: Lock out foreign keys to allow table swapping
    c.execute("PRAGMA foreign_keys = OFF")
    
    # ---------------------------------------------------------
    # 1. Fetch Legacy Data (OUTSIDE TRANSACTION)
    # ---------------------------------------------------------
    c.execute("SELECT * FROM erp_parts")
    legacy_parts = [dict(row) for row in c.fetchall()]
    
    # Build global category lookup map
    c.execute("SELECT name, id FROM erp_categories")
    category_map = {row['name']: row['id'] for row in c.fetchall()}

    # ---------------------------------------------------------
    # 2. Execute Atomic I/O (INSIDE TRANSACTION)
    # ---------------------------------------------------------
    c.execute("BEGIN TRANSACTION")
    try:
        # Ledger Rebuild
        c.execute("""
            CREATE TABLE erp_parts_v2 (
                part_id TEXT PRIMARY KEY,
                nomenclature TEXT NOT NULL,
                category_id TEXT NOT NULL REFERENCES erp_categories(id),
                quantity_on_hand INTEGER NOT NULL DEFAULT 0,
                reorder_threshold INTEGER NOT NULL DEFAULT 5,
                unit_cost REAL NOT NULL DEFAULT 0.0
            )
        """)
        
        # Data Porting & Global Category Binding
        for part in legacy_parts:
            legacy_category_name = part['category']
            if not legacy_category_name or str(legacy_category_name).strip() == "":
                legacy_category_name = "UNCATEGORIZED"
                
            category_id = None
            
            if legacy_category_name:
                if legacy_category_name in category_map:
                    category_id = category_map[legacy_category_name]
                else:
                    # Synthesize missing category to maintain physical domain integrity
                    new_category_id = f"CAT-{uuid.uuid4().hex[:6].upper()}"
                    c.execute("INSERT INTO erp_categories (id, name) VALUES (?, ?)", (new_category_id, legacy_category_name))
                    category_map[legacy_category_name] = new_category_id
                    category_id = new_category_id

            # Insert into normalized ledger (Financial/Threshold strict preservation)
            c.execute("""
                INSERT INTO erp_parts_v2 
                (part_id, nomenclature, category_id, quantity_on_hand, reorder_threshold, unit_cost)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                part['part_id'],
                part['nomenclature'],
                category_id,
                int(part['quantity_on_hand']),
                int(part['reorder_threshold']),
                float(part['unit_cost'])
            ))
            
        # Atomic Swap
        c.execute("DROP TABLE erp_parts")
        c.execute("ALTER TABLE erp_parts_v2 RENAME TO erp_parts")
        
        # ---------------------------------------------------------
        # 3. Pre-Commit Integrity Guard
        # ---------------------------------------------------------
        c.execute("PRAGMA foreign_key_check(erp_parts)")
        fk_violations = c.fetchall()
        if fk_violations:
            raise sqlite3.IntegrityError(f"Relational binding failure detected prior to commit: {fk_violations}")
        
        # Physically seal the transaction only if integrity checks pass
        conn.commit()
        print("[SUCCESS] Phase 35.4 Migration complete. erp_parts structurally normalized.")
        
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
