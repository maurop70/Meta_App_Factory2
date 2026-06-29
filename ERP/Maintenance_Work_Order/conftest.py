"""
Shared WS-A1 test harness.

Provisions a throwaway tenant the REAL way (agent_matrix._seed_tenant_baseline) and
yields a TestClient whose Host header routes every call to that tenant's DB via the
running app's own TenantContextMiddleware -- the same path production uses. The
X-Tenant-Id response header (stamped by the middleware) is the positive control: a
misbind to the default DB fails loudly here instead of producing green-but-meaningless
assertions downstream.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import maintenance_backend as mb  # noqa: E402  (import triggers init_tables() -> default DB seeded)
import agent_matrix as am  # noqa: E402
import local_db  # noqa: E402
from local_db import get_db_connection_for_tenant, _resolve_tenant_db_path  # noqa: E402

TENANT = "wsa1test"
# A 3+-label Host whose leftmost label IS the tenant: _resolve_tenant_from_host routes
# every request to TENANT's DB. We do NOT call set_current_tenant -- the middleware
# re-binds per request from this Host, overwriting any contextvar the fixture sets.
_TENANT_BASE_URL = f"http://{TENANT}.example.com"

_identity = {"payload": {"sub": "ERP-1000", "role": "ADMINISTRATOR", "jti": "test"}}


def as_user(sub, role):
    """Override the JWT identity dependency. Hoisted here so both test modules can
    import it (otherwise the new suite would not collect)."""
    _identity["payload"] = {"sub": sub, "role": role, "jti": "test"}
    mb.app.dependency_overrides[mb.verify_jwt_token] = lambda: _identity["payload"]


def _forget_tenant():
    """Drop the bootstrap memo so the next provision re-clones a fresh file."""
    with local_db._tenant_init_lock:
        local_db._initialized_tenants.discard(TENANT)


@pytest.fixture
def tenant_client():
    """Provision tenant 'wsa1test' via _seed_tenant_baseline, yield a Host-routed
    TestClient, then remove the tenant file so data/tenants/ returns to empty."""
    db_path = _resolve_tenant_db_path(TENANT)
    _forget_tenant()
    if os.path.exists(db_path):
        os.remove(db_path)  # clean slate: no stale MWO row / admin collision

    conn = get_db_connection_for_tenant(TENANT)  # clones schema (no rows) from the default DB
    try:
        am._seed_tenant_baseline(conn)  # canonical-6 roles + LOC-DEFAULT + ERP-1000 admin
    finally:
        conn.close()

    client = TestClient(mb.app, base_url=_TENANT_BASE_URL)

    # POSITIVE CONTROL: prove the app resolved THIS request to wsa1test, not default.
    # X-Tenant-Id is stamped by the middleware regardless of the route's auth outcome.
    probe = client.get("/api/admin/roles")
    assert probe.headers.get("X-Tenant-Id") == TENANT, (
        f"TENANT MISBIND: app routed to {probe.headers.get('X-Tenant-Id')!r}, not {TENANT!r}; "
        f"every downstream assertion would be validating the wrong DB."
    )

    try:
        yield client
    finally:
        mb.app.dependency_overrides.clear()
        _forget_tenant()
        if os.path.exists(db_path):
            os.remove(db_path)  # keep data/tenants/ empty (CI-isolation invariant)
