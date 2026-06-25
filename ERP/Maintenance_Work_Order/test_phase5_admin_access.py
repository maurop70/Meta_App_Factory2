"""
Phase 5 / Verification Plan #1 — Administrator RBAC lockout is resolved.

A GET /admin/users request carrying an ADMINISTRATOR JWT must return 200 (the
Phase 1 fix changed `actor_role != "ADMIN"` to `actor_role not in
["ADMINISTRATOR", "ADMIN"]`). Exercises the real route in-process via TestClient,
overriding verify_jwt_token so no RS256 gateway is required.

Run: venv/Scripts/python.exe -m pytest test_phase5_admin_access.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402
import maintenance_backend as mb  # noqa: E402

app = mb.app
client = TestClient(app)

_identity = {"payload": {"sub": "ERP-1000", "role": "ADMINISTRATOR", "jti": "test"}}


def as_user(sub, role):
    # Re-install the override on every switch: these Phase 5 files share the
    # module-singleton `app`, so whichever file imported last would otherwise own
    # the override. Reinstalling here makes the active override read THIS file's
    # identity, keeping the tests isolated when run together under pytest.
    _identity["payload"] = {"sub": sub, "role": role, "jti": "test"}
    app.dependency_overrides[mb.verify_jwt_token] = lambda: _identity["payload"]


def test_administrator_can_list_users():
    """ADMINISTRATOR (not just ADMIN) clears the admin user-list RBAC gate."""
    as_user("ERP-1000", "ADMINISTRATOR")
    r = client.get("/api/admin/users")
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    assert isinstance(r.json(), list), "user list endpoint should return a JSON array"


def test_admin_alias_still_allowed():
    """The legacy ADMIN role must keep working alongside ADMINISTRATOR."""
    as_user("TEST-ADMIN", "ADMIN")
    r = client.get("/api/admin/users")
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"


def test_non_admin_is_rejected():
    """A non-privileged role must still be locked out (403), proving the gate
    didn't simply get removed."""
    as_user("TEST-TECH", "TECH")
    r = client.get("/api/admin/users")
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([os.path.abspath(__file__), "-v"]))
