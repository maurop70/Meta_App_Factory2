import sqlite3

def execute_schema_migration(db_path: str):
    conn = sqlite3.connect(db_path)
    # Enforce foreign key constraints at connection level
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    
    try:
        # Phase 1: Idempotent Structural Appends
        cursor.execute("PRAGMA table_info(users);")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_active' not in existing_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;")
        if 'token_version' not in existing_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1;")
        
        # Phase 2: Instantiation of the Audit Telemetry Ledger (Strict FKs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_audit_logs (
                event_id TEXT PRIMARY KEY,
                target_user_id TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                timestamp DATETIME DEFAULT (datetime('now', 'utc')),
                FOREIGN KEY (target_user_id) REFERENCES users(user_id),
                FOREIGN KEY (actor_user_id) REFERENCES users(user_id)
            );
        """)
        
        # Phase 3: Engine-Level Immutability Locks
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS prevent_audit_update
            BEFORE UPDATE ON user_audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'STRUCTURAL VIOLATION: Audit telemetry is strictly immutable.');
            END;
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
            BEFORE DELETE ON user_audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'STRUCTURAL VIOLATION: Audit telemetry is strictly immutable.');
            END;
        """)
        
        # Phase 4: Performance Indexing
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_target ON user_audit_logs(target_user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON user_audit_logs(actor_user_id);")
        
        conn.commit()
        print("SUCCESS: Idempotent and immutable enterprise schema migration completed.")
    except Exception as e:
        conn.rollback()
        print(f"FATAL SCHEMA ERROR: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    execute_schema_migration("data/maintenance_erp.db")
