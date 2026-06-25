"""
Phase 5 / Verification Plan #3 — Dynamic role creation.

POST /admin/roles {role_name: 'SUPERVISOR'} must succeed and the new role must
then appear both in GET /admin/roles and directly in the erp_roles registry.
Tears the role back out afterwards.

Run: venv/Scripts/python.exe -m pytest test_phase5_dynamic_role.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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


ROLE = "SUPERVISOR"


def _cleanup():
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM erp_roles WHERE role_name = ?", (ROLE,))
        conn.commit()
    finally:
        conn.close()


def test_create_dynamic_role():
    as_user("ERP-1000", "ADMINISTRATOR")
    _cleanup()
    try:
        r = client.post("/api/admin/roles", json={"role_name": ROLE.lower()})  # lower -> normalized
        assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"

        # Visible via the registry endpoint
        r2 = client.get("/api/admin/roles")
        assert r2.status_code == 200, r2.text
        names = {x["role_name"] for x in r2.json().get("data", [])}
        assert ROLE in names, f"{ROLE} not in GET /admin/roles: {sorted(names)}"

        # Present directly in erp_roles
        conn = get_db_connection()
        try:
            hit = conn.execute(
                "SELECT 1 FROM erp_roles WHERE role_name = ?", (ROLE,)).fetchone()
        finally:
            conn.close()
        assert hit is not None, f"{ROLE} not persisted to erp_roles"

        # Custom role is NOT flagged system-default
        supervisor = next(x for x in r2.json()["data"] if x["role_name"] == ROLE)
        assert supervisor.get("is_system_default") is False
    finally:
        _cleanup()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([os.path.abspath(__file__), "-v"]))
