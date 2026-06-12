"""
[BACK OFFICE INVENTORY MODULE] Schema Migration
Creates supplier / purchase-order / manual-log tables, extends erp_skus with
supplier + category linkage, rebuilds erp_employees to admit the CFO role,
and seeds suppliers, administrative SKUs, and the CFO operator identity.

Idempotent: safe to execute multiple times.
"""
import os
import shutil
import sqlite3
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_here, "data", "maintenance_erp.db")
GATEWAY_DB_PATH = os.path.join(os.path.dirname(_here), "Module_0_Gateway", "data", "gateway_core.db")

CFO_EMP_ID = "ERP-5000"
CFO_PIN = "4567"


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def migrate_erp_database():
    # Cold backup before structural mutation
    backup_path = os.path.join(_here, "archives", f"maintenance_erp.pre_inventory.{int(time.time())}.db")
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy2(DB_PATH, backup_path)
    print(f"[BACKUP] {backup_path}")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys=OFF;")
    cursor.execute("BEGIN IMMEDIATE TRANSACTION")

    # --- 1. Supplier Directory ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS erp_suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            default_lead_time_days INTEGER DEFAULT 7,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- 2. Purchase Order Master ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS erp_purchase_orders (
            po_id TEXT PRIMARY KEY,
            supplier_id TEXT REFERENCES erp_suppliers(supplier_id),
            status TEXT CHECK(status IN ('DRAFT', 'PENDING_CFO', 'APPROVED', 'HOLD', 'REJECTED', 'FULFILLED')) DEFAULT 'DRAFT',
            priority INTEGER DEFAULT 0,
            eta_date TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            submitted_at TIMESTAMP,
            decided_at TIMESTAMP
        )
    ''')
    # Concurrency shield: exactly one open DRAFT per supplier (mirrors erp_procurement_queue doctrine)
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_po_one_draft_per_supplier
        ON erp_purchase_orders(supplier_id) WHERE status = 'DRAFT'
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_po_status ON erp_purchase_orders(status)")

    # --- 3. Purchase Order Line Items ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS erp_purchase_order_items (
            po_id TEXT REFERENCES erp_purchase_orders(po_id) ON DELETE CASCADE,
            sku_id TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_cost REAL NOT NULL,
            PRIMARY KEY (po_id, sku_id)
        )
    ''')

    # --- 4. Zero-Trust Manual Adjustment Log ---
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

    # --- 5. erp_skus alterations: supplier + administrative classification ---
    if not _column_exists(cursor, "erp_skus", "supplier_id"):
        cursor.execute("ALTER TABLE erp_skus ADD COLUMN supplier_id TEXT REFERENCES erp_suppliers(supplier_id)")
        print("[DDL] erp_skus.supplier_id added")
    if not _column_exists(cursor, "erp_skus", "category_id"):
        cursor.execute("ALTER TABLE erp_skus ADD COLUMN category_id TEXT REFERENCES erp_categories(id)")
        print("[DDL] erp_skus.category_id added")
    if not _column_exists(cursor, "erp_skus", "min_order_qty"):
        cursor.execute("ALTER TABLE erp_skus ADD COLUMN min_order_qty INTEGER DEFAULT 1")
        print("[DDL] erp_skus.min_order_qty added")

    # --- 6. Rebuild erp_employees with CFO admitted to the role CHECK ---
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='erp_employees'")
    ddl = cursor.fetchone()[0]
    if "'CFO'" not in ddl:
        cursor.execute('''
            CREATE TABLE erp_employees_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('ADMINISTRATOR', 'ADMIN', 'DM', 'HM', 'TECH', 'CFO')),
                pin_hash TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                department_id TEXT REFERENCES erp_departments(id),
                reports_to_hm_id TEXT REFERENCES erp_employees(id)
            )
        ''')
        cursor.execute('''
            INSERT INTO erp_employees_new
            SELECT id, name, role, pin_hash, is_active, department_id, reports_to_hm_id FROM erp_employees
        ''')
        cursor.execute("DROP TABLE erp_employees")
        cursor.execute("ALTER TABLE erp_employees_new RENAME TO erp_employees")
        print("[DDL] erp_employees rebuilt with CFO role clearance")

    # --- 7. Seed data ---
    cursor.execute('''
        INSERT OR IGNORE INTO erp_suppliers (supplier_id, name, email, default_lead_time_days) VALUES
        ('SUP-MAINT-01', 'Industrial Components Co.', 'orders@industrial-components.example.com', 7),
        ('SUP-ADMIN-01', 'OfficePro Supplies Ltd.',  'sales@officepro-supplies.example.com', 3)
    ''')

    cursor.execute("INSERT OR IGNORE INTO erp_categories (id, name) VALUES ('CAT-ADMIN', 'Administrative Supplies')")
    cursor.execute("INSERT OR IGNORE INTO erp_categories (id, name) VALUES ('CAT-MAINT', 'Maintenance Parts')")

    # Existing maintenance SKUs default to the maintenance supplier/category
    cursor.execute("UPDATE erp_skus SET supplier_id = 'SUP-MAINT-01' WHERE supplier_id IS NULL")
    cursor.execute("UPDATE erp_skus SET category_id = 'CAT-MAINT' WHERE category_id IS NULL")

    # Administrative supply SKUs (stationery taxonomy)
    cursor.execute('''
        INSERT OR IGNORE INTO erp_skus (sku_id, nomenclature, unit_cost, reorder_threshold, quantity_on_hand, supplier_id, category_id) VALUES
        ('SKU-ADM-001', 'A4 Copy Paper (500-Sheet Ream)', 6.50, 20, 50, 'SUP-ADMIN-01', 'CAT-ADMIN'),
        ('SKU-ADM-002', 'Ballpoint Pens (Box of 12)',     4.25, 10, 25, 'SUP-ADMIN-01', 'CAT-ADMIN'),
        ('SKU-ADM-003', 'Printer Toner Cartridge (Black)', 89.00, 5, 8, 'SUP-ADMIN-01', 'CAT-ADMIN'),
        ('SKU-ADM-004', 'Sticky Notes (Pack of 12 Pads)',  7.80, 8, 15, 'SUP-ADMIN-01', 'CAT-ADMIN')
    ''')

    # Minimum Order Quantities for bulk-packaged admin supplies (idempotent).
    # Copy paper ships by the 5-ream carton; toner by the 2-cartridge pack.
    cursor.execute("UPDATE erp_skus SET min_order_qty = 5 WHERE sku_id = 'SKU-ADM-001' AND (min_order_qty IS NULL OR min_order_qty = 1)")
    cursor.execute("UPDATE erp_skus SET min_order_qty = 2 WHERE sku_id = 'SKU-ADM-003' AND (min_order_qty IS NULL OR min_order_qty = 1)")

    # CFO operator identity (local ERP ledger)
    import bcrypt
    cfo_hash = bcrypt.hashpw(CFO_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    cursor.execute("SELECT 1 FROM erp_employees WHERE id = ?", (CFO_EMP_ID,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO erp_employees (id, name, role, pin_hash, is_active, department_id) VALUES (?, ?, 'CFO', ?, 1, 'DEP-108E72')",
            (CFO_EMP_ID, "Chief Financial Officer", cfo_hash)
        )
        print(f"[SEED] CFO identity {CFO_EMP_ID} provisioned in ERP ledger")

    conn.commit()
    cursor.execute("PRAGMA foreign_keys=ON;")
    conn.close()
    print("[OK] maintenance_erp.db migration complete")
    return cfo_hash


def migrate_gateway_database(cfo_hash: str):
    """Provision the CFO login identity in the Module 0 Gateway so JWTs carry role=CFO."""
    if not os.path.exists(GATEWAY_DB_PATH):
        print(f"[WARN] Gateway DB not found at {GATEWAY_DB_PATH}; skipping CFO login provisioning.")
        return
    conn = sqlite3.connect(GATEWAY_DB_PATH, timeout=30)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM erp_employees WHERE emp_id = ?", (CFO_EMP_ID,))
    if not cursor.fetchone():
        import uuid
        cursor.execute('''
            INSERT INTO erp_employees
            (id, emp_id, name, first_name, last_name, role, pin, pin_hash, is_active, department_id, reports_to_hm_id, status, department)
            VALUES (?, ?, ?, ?, ?, 'CFO', ?, ?, 1, NULL, NULL, 'ACTIVE', 'Finance')
        ''', (f"U-{uuid.uuid4().hex[:6].upper()}", CFO_EMP_ID, "Chief Financial Officer",
              "Chief", "Financial Officer", CFO_PIN, cfo_hash))
        conn.commit()
        print(f"[SEED] CFO identity {CFO_EMP_ID} provisioned in Gateway (PIN {CFO_PIN})")
    else:
        print("[SKIP] CFO identity already present in Gateway")
    conn.close()


def verify():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    required = ["erp_suppliers", "erp_purchase_orders", "erp_purchase_order_items", "erp_inventory_manual_logs"]
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    missing = [t for t in required if t not in tables]
    if missing:
        raise SystemExit(f"[FAIL] Missing tables after migration: {missing}")
    cursor.execute("SELECT COUNT(*) FROM erp_suppliers")
    suppliers = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM erp_skus WHERE category_id = 'CAT-ADMIN'")
    admin_skus = cursor.fetchone()[0]
    cursor.execute("SELECT role FROM erp_employees WHERE id = ?", (CFO_EMP_ID,))
    cfo = cursor.fetchone()
    conn.close()
    print(f"[VERIFY] suppliers={suppliers}, admin_skus={admin_skus}, cfo_role={cfo[0] if cfo else 'MISSING'}")
    if suppliers < 2 or admin_skus < 4 or not cfo or cfo[0] != "CFO":
        raise SystemExit("[FAIL] Seed verification failed")
    print("[VERIFY] Migration integrity confirmed.")


if __name__ == "__main__":
    cfo_hash = migrate_erp_database()
    migrate_gateway_database(cfo_hash)
    verify()
