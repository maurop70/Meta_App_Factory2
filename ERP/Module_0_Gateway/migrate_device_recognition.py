"""
Idempotent migration for Smart Device Recognition + custom credentials.

Applies to Module_0_Gateway/data/gateway_core.db:
  1. Adds nullable username / phone_number columns to erp_employees.
  2. Creates partial UNIQUE indexes (SQLite cannot ADD COLUMN ... UNIQUE,
     and partial indexes allow many NULLs while enforcing uniqueness on values).
  3. Creates the erp_user_devices table, keyed to erp_employees(emp_id).

Safe to run multiple times.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "gateway_core.db"


def _column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def run():
    if not DB_PATH.exists():
        raise SystemExit(f"Gateway DB not found at {DB_PATH}. Seed it before migrating.")

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # 1. Nullable identity columns
    for col in ("username", "phone_number"):
        if not _column_exists(cur, "erp_employees", col):
            cur.execute(f"ALTER TABLE erp_employees ADD COLUMN {col} TEXT")
            print(f"  Added column erp_employees.{col}")
        else:
            print(f"  Column erp_employees.{col} already present")

    # 2. Partial UNIQUE indexes (enforce uniqueness only on non-null values)
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_username "
        "ON erp_employees(username) WHERE username IS NOT NULL"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_phone "
        "ON erp_employees(phone_number) WHERE phone_number IS NOT NULL"
    )

    # 3. Recognized-device registry
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_user_devices (
            device_id    TEXT PRIMARY KEY,
            emp_id       TEXT REFERENCES erp_employees(emp_id) ON DELETE CASCADE,
            device_name  TEXT,
            device_type  TEXT CHECK(device_type IN ('mobile', 'desktop')),
            last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()
    print("Device-recognition migration complete.")


if __name__ == "__main__":
    run()
