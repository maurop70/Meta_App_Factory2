import os
import re
import sqlite3
import shutil
import threading
import contextvars
import logging

logger = logging.getLogger("LocalDB")

_here = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_here, "data")
DB_PATH = os.path.join(DATA_DIR, "maintenance_erp.db")

# --- Multi-tenant storage ---------------------------------------------------
# Each tenant gets a fully isolated SQLite file under data/tenants/. The default
# database above remains the fallback for the admin command console and any
# request that does not carry an explicit tenant context.
TENANTS_DIR = os.path.join(DATA_DIR, "tenants")

# The reserved id that routes back to the legacy default database.
DEFAULT_TENANT_ID = "default"

# A valid tenant_id is a DNS-label-safe slug: lowercase alphanumerics with
# optional internal hyphens, 1-63 chars. This allowlist is the PRIMARY defence
# against path traversal -- '/', '\\', '.' and '..' can never satisfy it.
_TENANT_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

# Guards first-time tenant provisioning so two concurrent requests cannot race
# to create / bootstrap the same database file. The set memoises tenants whose
# schema has already been ensured this process, keeping the hot path lock-free.
_tenant_init_lock = threading.Lock()
_initialized_tenants = set()

# The active tenant for the current execution context (request or background
# task). When unset, connections fall back to the default database, so any code
# path with no tenant bound (lifespan boot, scripts) behaves exactly as before.
# contextvars are both asyncio-task-safe and copied into worker threads, so this
# binding survives FastAPI running sync routes in its threadpool.
_current_tenant_id = contextvars.ContextVar("current_tenant_id", default=None)


def set_current_tenant(tenant_id):
    """Bind ``tenant_id`` to the current execution context. Returns a token that
    MUST be passed to reset_current_tenant() to restore the prior binding."""
    return _current_tenant_id.set(tenant_id)


def reset_current_tenant(token) -> None:
    """Restore the tenant binding captured by a prior set_current_tenant()."""
    _current_tenant_id.reset(token)


def get_current_tenant():
    """Return the tenant bound to the current context, or None if unbound."""
    return _current_tenant_id.get()


def _apply_connection_pragmas(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Apply the strict concurrency / integrity pragmas shared by every
    connection (default and per-tenant alike)."""
    # Return dictionary-like rows to mimic JSON responses from the previous API
    conn.row_factory = sqlite3.Row

    # Enforce strict SQLite pragmas for concurrency and data integrity
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    return conn

def _connect_default() -> sqlite3.Connection:
    """Open a connection to the default database, bypassing tenant routing.
    Connects to the LOCAL copy outside Google Drive to prevent file lock deadlocks.
    isolation_level=None forces autocommit mode, empowering routes to explicitly
    declare BEGIN IMMEDIATE TRANSACTION boundaries for concurrency locking."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10, isolation_level=None)
    return _apply_connection_pragmas(conn)


def get_default_db_connection() -> sqlite3.Connection:
    """Open a connection to the default GLOBAL database, bypassing tenant context
    routing entirely. Use this for cross-tenant/global tables that must never be
    partitioned per tenant -- e.g. the revoked-token (JTI) blacklist and auth
    rate limits -- so a tenant-bound request cannot read an empty per-tenant copy
    and miss a globally-revoked token."""
    return _connect_default()


def get_db_connection() -> sqlite3.Connection:
    """
    Returns a thread-safe connection object with strict concurrency pragmas.

    Tenant-aware: if a tenant is bound to the current execution context (see
    set_current_tenant / TenantContextMiddleware), the connection is transparently
    routed to that tenant's isolated database. With no tenant bound -- the admin
    command console, lifespan boot, CLI scripts -- it falls back to the default
    database, preserving the pre-multi-tenant behaviour exactly.
    """
    tenant_id = _current_tenant_id.get()
    if tenant_id and tenant_id != DEFAULT_TENANT_ID:
        return get_db_connection_for_tenant(tenant_id)
    return _connect_default()


def _validate_tenant_id(tenant_id) -> str:
    """Normalise and strictly validate a tenant_id, raising ValueError on any
    value that is not a DNS-label-safe slug. This is the path-traversal guard."""
    if not isinstance(tenant_id, str):
        raise ValueError(f"tenant_id must be a string, got {type(tenant_id).__name__}")
    normalized = tenant_id.strip().lower()
    if not _TENANT_ID_RE.match(normalized):
        raise ValueError(f"Invalid tenant_id (must be a 1-63 char DNS label): {tenant_id!r}")
    return normalized


def _resolve_tenant_db_path(tenant_id: str) -> str:
    """Resolve the on-disk path for a validated tenant_id, with a defence-in-depth
    containment check ensuring the realpath can never escape data/tenants/."""
    candidate = os.path.join(TENANTS_DIR, f"tenant_{tenant_id}.db")
    tenants_root = os.path.realpath(TENANTS_DIR)
    resolved = os.path.realpath(candidate)
    # commonpath raises ValueError across drives; a mismatch means traversal.
    if os.path.commonpath([tenants_root, resolved]) != tenants_root:
        raise ValueError(f"Resolved tenant path escapes tenant root: {tenant_id!r}")
    return resolved


def _bootstrap_tenant_schema(conn: sqlite3.Connection) -> None:
    """
    Create the full ERP schema in a freshly-provisioned tenant database.

    The authoritative schema is the live default database -- the cumulative
    product of setup_db.py plus every migration script. We clone its DDL
    (tables / indexes / triggers / views) verbatim so each tenant is an exact
    structural mirror of production; NO rows are copied, preserving isolation.

    Foreign-key enforcement is disabled during creation so the order in which
    objects are replayed cannot trip referential checks on not-yet-created
    parents. If the template is unavailable we fall back to the init_tables()
    base subset and log loudly, because that subset is known to be incomplete
    (it omits erp_employees, work_orders, erp_skus, etc.).
    """
    if not os.path.exists(DB_PATH):
        logger.warning(
            "Authoritative template %s not found; falling back to the INCOMPLETE "
            "init_tables() base schema for tenant bootstrap.", DB_PATH
        )
        _create_base_tables(conn)
        return

    src = sqlite3.connect(DB_PATH)
    try:
        ddl_objects = src.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
            "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END"
        ).fetchall()
    finally:
        src.close()

    conn.execute("PRAGMA foreign_keys=OFF;")
    try:
        for (ddl,) in ddl_objects:
            conn.execute(ddl)
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON;")
    logger.info(
        "Provisioned tenant schema by cloning %d objects from %s",
        len(ddl_objects), DB_PATH,
    )


def get_db_connection_for_tenant(tenant_id) -> sqlite3.Connection:
    """
    Resolve and return a thread-safe connection to an isolated tenant database
    at data/tenants/tenant_<id>.db.

    - ``tenant_id`` is strictly validated against a DNS-label allowlist, blocking
      path traversal before any filesystem access.
    - A ``None`` / empty id, or the reserved id "default", routes to the legacy
      default database so the existing admin command console is never disturbed.
      (Uses _connect_default() directly, not get_db_connection(), so an explicit
      "default" request is honoured even when another tenant is context-bound.)
    - On first use this process, the tenant file is created and its schema is
      bootstrapped to mirror production. Provisioning is serialised by a lock so
      concurrent requests cannot double-create the file.
    """
    if tenant_id is None or (
        isinstance(tenant_id, str) and tenant_id.strip().lower() in ("", DEFAULT_TENANT_ID)
    ):
        return _connect_default()

    tenant_id = _validate_tenant_id(tenant_id)
    db_path = _resolve_tenant_db_path(tenant_id)

    # Fast path: schema already ensured this process. Double-checked under lock.
    if tenant_id not in _initialized_tenants:
        with _tenant_init_lock:
            if tenant_id not in _initialized_tenants:
                os.makedirs(TENANTS_DIR, exist_ok=True)
                needs_bootstrap = not os.path.exists(db_path)
                conn = sqlite3.connect(
                    db_path, check_same_thread=False, timeout=10, isolation_level=None
                )
                _apply_connection_pragmas(conn)
                try:
                    if needs_bootstrap:
                        _bootstrap_tenant_schema(conn)
                finally:
                    conn.close()
                _initialized_tenants.add(tenant_id)

    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10, isolation_level=None)
    return _apply_connection_pragmas(conn)


def _create_base_tables(conn: sqlite3.Connection) -> None:
    """Create the base table subset defined inline in this module against the
    given connection. NOTE: this subset is intentionally narrow and is NOT the
    complete production schema (see _bootstrap_tenant_schema)."""
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
        raise


def init_tables():
    """Ensure the base table subset exists in the default database. Owns the
    connection lifecycle (open + close); the DDL itself lives in
    _create_base_tables so it can be reused for tenant fallback bootstrap."""
    conn = get_db_connection()
    try:
        _create_base_tables(conn)
    except Exception as e:
        logger.error(f"Failed to initialize tables: {e}")
    finally:
        conn.close()

# Initialize schema on load
init_tables()
