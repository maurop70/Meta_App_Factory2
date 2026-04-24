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
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to initialize tables: {e}")
    finally:
        conn.close()

# Initialize schema on load
init_tables()
