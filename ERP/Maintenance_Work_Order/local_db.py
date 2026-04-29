import os
import sqlite3
import shutil
import logging

logger = logging.getLogger("LocalDB")

_here = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_here, "data", "maintenance_erp.db")

def get_db_connection() -> sqlite3.Connection:
    """
    Returns a thread-safe connection object with strict concurrency pragmas.
    Connects to the LOCAL copy outside Google Drive to prevent file lock deadlocks.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    
    # Return dictionary-like rows to mimic JSON responses from the previous API
    conn.row_factory = sqlite3.Row
    
    # Enforce strict SQLite pragmas for concurrency and data integrity
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    
    return conn

def init_tables():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('ADMIN', 'HD', 'HM', 'TECH')),
                department TEXT,
                reports_to_hm_id TEXT,
                FOREIGN KEY(reports_to_hm_id) REFERENCES users(user_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warehouse_inventory (
                sku TEXT PRIMARY KEY,
                stock_level INTEGER,
                unit_cost FLOAT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auth_rate_limits (
                employee_id TEXT NOT NULL,
                attempt_timestamp INTEGER NOT NULL
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_rate_limits_emp ON auth_rate_limits(employee_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_rate_limits_time ON auth_rate_limits(attempt_timestamp)")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_equipment (
                equipment_id TEXT PRIMARY KEY,
                nomenclature TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'DEGRADED', 'OFFLINE')),
                department TEXT NOT NULL,
                assigned_tech_id TEXT,
                FOREIGN KEY(assigned_tech_id) REFERENCES erp_employees(id)
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipment_dept_status ON erp_equipment(department, status)")
        
        # [PHASE 34.9] Master Parts Catalog
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_parts (
                part_id TEXT PRIMARY KEY,
                nomenclature TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity_on_hand INTEGER NOT NULL DEFAULT 0 CHECK(quantity_on_hand >= 0),
                reorder_threshold INTEGER NOT NULL DEFAULT 5,
                unit_cost REAL NOT NULL DEFAULT 0.0
            )
        ''')
        
        # [PHASE 34.9] Append-Only Consumption Ledger
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_inventory_ledger (
                transaction_id TEXT PRIMARY KEY,
                part_id TEXT NOT NULL,
                mwo_id TEXT NOT NULL,
                tech_id TEXT NOT NULL,
                quantity_consumed INTEGER NOT NULL CHECK(quantity_consumed > 0),
                transaction_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(part_id) REFERENCES erp_parts(part_id),
                FOREIGN KEY(mwo_id) REFERENCES work_orders(mwo_id),
                FOREIGN KEY(tech_id) REFERENCES erp_employees(id)
            )
        ''')
        
        # Mandatory indexing for cross-referencing consumption by MWO and reporting
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_mwo ON erp_inventory_ledger(mwo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_part ON erp_inventory_ledger(part_id)")
        
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to initialize tables: {e}")
    finally:
        conn.close()

# Initialize schema on load
init_tables()
