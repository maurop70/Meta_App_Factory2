import sqlite3
import os

def synthesize_procurement_ledger():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute("BEGIN TRANSACTION")
    try:
        # 1. Ledger Creation
        c.execute("""
            CREATE TABLE IF NOT EXISTS erp_procurement_queue (
                procurement_id TEXT PRIMARY KEY,
                part_id TEXT NOT NULL REFERENCES erp_parts(part_id),
                triggered_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'APPROVED', 'FULFILLED', 'REJECTED'))
            )
        """)
        
        # 2. Structural Concurrency Guardrail (Partial Index)
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_active_procurement 
            ON erp_procurement_queue (part_id) 
            WHERE status IN ('PENDING', 'APPROVED')
        """)
        
        conn.commit()
        print("[SUCCESS] erp_procurement_queue synthesized. Concurrency locks active.")
    except Exception as e:
        conn.rollback()
        print(f"[FATAL] Schema synthesis failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    synthesize_procurement_ledger()
