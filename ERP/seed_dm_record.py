"""Seed the missing ERP-4000 DM record into erp_employees.

The QA Lab auth gateway issues tokens for ERP-4000 (DM persona), but the
maintenance DB has no matching erp_employees row, so /api/dm/personnel
404s. Insert the DM record (and its department) idempotently.

Auth verification is delegated to the gateway, so pin_hash only needs to
satisfy the NOT NULL constraint.
"""

import sqlite3
import sys
import os

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Maintenance_Work_Order", "data", "maintenance_erp.db",
)

DUMMY_PIN_HASH = "$2b$12$gateway.delegated.auth.placeholder.hash.not.used000000"

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute(
    "INSERT OR IGNORE INTO erp_departments (id, name) VALUES (?, ?)",
    ("DEPT-MECH", "Mechanical Maintenance"),
)
cur.execute(
    """INSERT OR IGNORE INTO erp_employees
       (id, name, role, pin_hash, is_active, department_id)
       VALUES (?, ?, ?, ?, 1, ?)""",
    ("ERP-4000", "Castro, Monica", "DM", DUMMY_PIN_HASH, "DEPT-MECH"),
)
conn.commit()

row = cur.execute(
    "SELECT id, name, role, department_id, is_active FROM erp_employees WHERE id='ERP-4000'"
).fetchone()
print(f"db: {DB}")
print(f"ERP-4000 row: {row}")
conn.close()
sys.exit(0 if row else 1)
