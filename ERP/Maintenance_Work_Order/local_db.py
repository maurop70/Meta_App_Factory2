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
    isolation_level=None forces autocommit mode, empowering routes to explicitly
    declare BEGIN IMMEDIATE TRANSACTION boundaries for concurrency locking.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10, isolation_level=None)
    
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
            CREATE TABLE IF NOT EXISTS revoked_tokens (
                jti TEXT PRIMARY KEY,
                revoked_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # [PHASE 35.1] Lookup Tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_categories (
                id   TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                manager_id TEXT REFERENCES erp_employees(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_departments (
                id   TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_equipment (
                equipment_id TEXT PRIMARY KEY,
                nomenclature TEXT NOT NULL,
                category_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'DEGRADED', 'OFFLINE', 'RETIRED')),
                department_id TEXT NOT NULL,
                assigned_tech_id TEXT,
                FOREIGN KEY(category_id) REFERENCES erp_categories(id),
                FOREIGN KEY(department_id) REFERENCES erp_departments(id),
                FOREIGN KEY(assigned_tech_id) REFERENCES erp_employees(id)
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipment_dept_status ON erp_equipment(department_id, status)")
        
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

        # [BACK OFFICE INVENTORY MODULE] Supplier directory
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_suppliers (
                supplier_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                default_lead_time_days INTEGER DEFAULT 7,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Incremental alteration safeguard for live databases created before
        # the supplier contact-detail expansion (phone / address).
        cursor.execute("PRAGMA table_info(erp_suppliers)")
        supplier_columns = {row[1] for row in cursor.fetchall()}
        if "phone" not in supplier_columns:
            cursor.execute("ALTER TABLE erp_suppliers ADD COLUMN phone TEXT")
        if "address" not in supplier_columns:
            cursor.execute("ALTER TABLE erp_suppliers ADD COLUMN address TEXT")

        # [BACK OFFICE INVENTORY MODULE] Purchase order master tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_purchase_orders (
                po_id TEXT PRIMARY KEY,
                supplier_id TEXT REFERENCES erp_suppliers(supplier_id),
                status TEXT CHECK(status IN ('DRAFT', 'PENDING_CFO', 'APPROVED', 'HOLD', 'REJECTED', 'FULFILLED')) DEFAULT 'DRAFT',
                priority INTEGER DEFAULT 0,
                eta_date TEXT,
                notes TEXT,
                cfo_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                submitted_at TIMESTAMP,
                decided_at TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_po_one_draft_per_supplier
            ON erp_purchase_orders(supplier_id) WHERE status = 'DRAFT'
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_po_status ON erp_purchase_orders(status)")

        # [BACK OFFICE INVENTORY MODULE] PO detail line items
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_purchase_order_items (
                po_id TEXT REFERENCES erp_purchase_orders(po_id) ON DELETE CASCADE,
                sku_id TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                unit_cost REAL NOT NULL,
                PRIMARY KEY (po_id, sku_id)
            )
        ''')

        # [BACK OFFICE INVENTORY MODULE] Zero-trust manual stock adjustment log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_inventory_manual_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku_id TEXT NOT NULL,
                direction TEXT CHECK(direction IN ('IN', 'OUT')) NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                comment TEXT,
                logged_by TEXT NOT NULL,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_logs_sku ON erp_inventory_manual_logs(sku_id)")

        # [RESTRICTED SKU PROCUREMENT] Employee -> SKU clearance junction.
        # Plain TEXT columns (no FKs) mirror the erp_purchase_order_items
        # convention: erp_employees / erp_skus are provisioned by separate
        # migration paths, so cross-init foreign keys would risk bootstrap
        # ordering failures. Referential cleanup is enforced in app code.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_employee_sku_access (
                employee_id TEXT NOT NULL,
                sku_id TEXT NOT NULL,
                PRIMARY KEY (employee_id, sku_id)
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_employee_sku_access_emp ON erp_employee_sku_access(employee_id)")

        conn.commit()
    except Exception as e:
        logger.error(f"Failed to initialize tables: {e}")
    finally:
        conn.close()

# Initialize schema on load
init_tables()
