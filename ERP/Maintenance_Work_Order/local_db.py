import os
import sqlite3
import shutil
import logging

logger = logging.getLogger("LocalDB")

# ═══════════════════════════════════════════════════════
# GOOGLE DRIVE DEADLOCK BYPASS
# ═══════════════════════════════════════════════════════
# SQLite requires exclusive OS-level file locks for WAL mode.
# Google Drive's virtual filesystem (FUSE/VFS) aggressively
# locks .db/.db-wal/.db-shm files, causing permanent deadlocks
# on synchronous reads. The database is relocated to a safe
# local directory outside the Drive sync boundary.
# ═══════════════════════════════════════════════════════

_here = os.path.dirname(os.path.abspath(__file__))
_DRIVE_DB_PATH = os.path.join(os.path.dirname(_here), "maintenance_erp.db")

# Safe local storage — completely outside Google Drive sync
_LOCAL_DB_DIR = os.path.join("C:\\", "erp_local_data")
DB_PATH = os.path.join(_LOCAL_DB_DIR, "maintenance_erp.db")

def _ensure_local_db():
    """
    Ensures the local DB exists. If it doesn't but the Drive copy does,
    copies it down as a one-time seed operation.
    """
    os.makedirs(_LOCAL_DB_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH) and os.path.exists(_DRIVE_DB_PATH):
        logger.info(f"Seeding local DB from Drive: {_DRIVE_DB_PATH} -> {DB_PATH}")
        shutil.copy2(_DRIVE_DB_PATH, DB_PATH)
    elif not os.path.exists(DB_PATH):
        logger.warning("No source DB found. A fresh database will be created.")

# Execute seed check on module import
_ensure_local_db()

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
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to initialize tables: {e}")
    finally:
        conn.close()

# Initialize schema on load
init_tables()
