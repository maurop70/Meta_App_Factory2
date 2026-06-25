"""
Phase 5 / Verification Plan #2 — Optional ingestion fields.

Bulk-imports an XLSX containing a TECH with a BLANK reports_to_hm_name AND a
BLANK pin_code, then asserts:
  * the import succeeds (HTTP 200),
  * the stored PIN hash verifies against the default '1234',
  * reports_to_hm_id is NULL in the ERP ledger,
  * the mirrored gateway row has username NULL (so the activation gate fires).

Uses an existing department ("Electrical Systems") so no stray department row is
created. Tears down the ingested employee from BOTH the ERP ledger and the
gateway IAM store.

Run: venv/Scripts/python.exe -m pytest test_phase5_optional_ingestion.py
"""
import io
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bcrypt  # noqa: E402
import openpyxl  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import maintenance_backend as mb  # noqa: E402
from local_db import get_db_connection  # noqa: E402

app = mb.app
client = TestClient(app)

_identity = {"payload": {"sub": "ERP-1000", "role": "ADMINISTRATOR", "jti": "test"}}


def as_user(sub, role):
    # Reinstall the override per call — see the note in test_phase5_admin_access:
    # these files share the module-singleton app, so the override must be
    # reasserted to read this file's identity when run together under pytest.
    _identity["payload"] = {"sub": sub, "role": role, "jti": "test"}
    app.dependency_overrides[mb.verify_jwt_token] = lambda: _identity["payload"]

TEST_NAME = "ZZ Bulk TechNoHM"
DEPT_NAME = "Electrical Systems"  # pre-existing (DEPT-ELEC) — avoids new dept rows


def _cleanup():
    # ERP ledger
    conn = get_db_connection()
    try:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM erp_employees WHERE name = ?", (TEST_NAME,)).fetchall()]
        conn.execute("DELETE FROM erp_employees WHERE name = ?", (TEST_NAME,))
        conn.commit()
    finally:
        conn.close()
    # Gateway IAM mirror
    if os.path.exists(mb.GATEWAY_DB_PATH):
        g = sqlite3.connect(mb.GATEWAY_DB_PATH)
        try:
            for emp_id in ids:
                g.execute("DELETE FROM erp_employees WHERE emp_id = ?", (emp_id,))
            g.commit()
        finally:
            g.close()


def _build_xlsx():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "role", "pin_code", "department_name", "reports_to_hm_name"])
    # blank pin_code and blank reports_to_hm_name (None cells)
    ws.append([TEST_NAME, "TECH", None, DEPT_NAME, None])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def test_optional_ingestion_blank_pin_and_hm():
    as_user("ERP-1000", "ADMINISTRATOR")
    _cleanup()
    try:
        content = _build_xlsx()
        r = client.post(
            "/api/admin/ingest/personnel/bulk",
            files={"file": (
                "personnel.xlsx", content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )},
        )
        assert r.status_code == 200, f"ingest failed: {r.status_code} {r.text}"

        # ERP ledger assertions
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT id, pin_hash, reports_to_hm_id FROM erp_employees WHERE name = ?",
                (TEST_NAME,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None, "ingested employee not found in ERP ledger"
        emp_id = row["id"]
        assert bcrypt.checkpw(b"1234", row["pin_hash"].encode()), "blank PIN did not default to '1234'"
        assert row["reports_to_hm_id"] is None, "blank reports_to_hm_name should yield NULL"

        # Gateway mirror: username NULL => activation gate (setup_required) fires
        assert os.path.exists(mb.GATEWAY_DB_PATH), "gateway DB not found"
        g = sqlite3.connect(mb.GATEWAY_DB_PATH)
        g.row_factory = sqlite3.Row
        try:
            grow = g.execute(
                "SELECT username FROM erp_employees WHERE emp_id = ?", (emp_id,)).fetchone()
        finally:
            g.close()
        assert grow is not None, "ingested employee not mirrored into gateway IAM store"
        assert grow["username"] is None, "gateway username must be NULL so the activation gate fires"
    finally:
        _cleanup()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([os.path.abspath(__file__), "-v"]))
