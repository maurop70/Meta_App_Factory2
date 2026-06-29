"""
WS-A1 — Role-registry contract (inverted from the legacy Phase-5 test).

Custom base-role minting is now DEFERRED to a future tier, so create_role is a
permanently-failing path: a non-canonical name returns 403, a canonical name 409
(already exists, not mintable anew), and canonical roles -- including VIEWER -- are
undeletable (400). Routed through the Host-bound tenant_client so the contract is
exercised against a real provisioned tenant (ERP-1000/ADMINISTRATOR present).

Run: venv/Scripts/python.exe -m pytest test_phase5_dynamic_role.py
"""
from conftest import as_user  # noqa: F401  (tenant_client fixture auto-discovered)


def test_custom_role_creation_blocked(tenant_client):
    as_user("ERP-1000", "ADMINISTRATOR")
    r = tenant_client.post("/api/admin/roles", json={"role_name": "supervisor"})
    assert r.status_code == 403, f"expected 403 (deferred), got {r.status_code}: {r.text}"


def test_canonical_role_create_is_conflict(tenant_client):
    as_user("ERP-1000", "ADMINISTRATOR")
    r = tenant_client.post("/api/admin/roles", json={"role_name": "viewer"})
    assert r.status_code == 409, f"expected 409 (already exists), got {r.status_code}: {r.text}"


def test_viewer_is_protected(tenant_client):
    as_user("ERP-1000", "ADMINISTRATOR")
    r = tenant_client.delete("/api/admin/roles/VIEWER")
    assert r.status_code == 400, f"expected 400 (canonical undeletable), got {r.status_code}: {r.text}"
