"""
WS-A1 — Canonical baseline seed (Section-3 acceptance).

Asserts, against a freshly provisioned tenant routed through the Host-bound client:
  * erp_roles == the canonical 6 exactly (no alias rows),
  * the DM description is locked to 'Department Manager' (highest-drift line),
  * erp_locations is non-empty (an empty table blocks MWO creation),
  * DISTINCT employee role across tenant ∪ gateway ⊆ canonical, with no TECHNICIAN,
  * a freshly provisioned tenant can immediately ingest a TECH and an HM, and that
    create_mwo on the seeded LOC-DEFAULT gets PAST role/auth + location validation and
    fails SPECIFICALLY on the equipment foreign key — the WS-A1 ↔ WS-A2 boundary.

Run: venv/Scripts/python.exe -m pytest test_phase5_canonical_seed.py
"""
import os
import sqlite3

from conftest import as_user, TENANT  # noqa: F401  (tenant_client fixture auto-discovered)
from local_db import get_db_connection_for_tenant, GATEWAY_DB_PATH

CANONICAL = {"ADMINISTRATOR", "HM", "DM", "TECH", "CFO", "VIEWER"}


def _tenant_conn():
    return get_db_connection_for_tenant(TENANT)


def test_registry_is_exactly_canonical_six(tenant_client):
    conn = _tenant_conn()
    try:
        names = {r[0] for r in conn.execute("SELECT role_name FROM erp_roles").fetchall()}
    finally:
        conn.close()
    assert names == CANONICAL, f"registry != canonical-6: {sorted(names)}"


def test_dm_description_locked(tenant_client):
    conn = _tenant_conn()
    try:
        desc = conn.execute("SELECT description FROM erp_roles WHERE role_name='DM'").fetchone()[0]
    finally:
        conn.close()
    assert desc == "Department Manager", f"DM description drifted: {desc!r}"


def test_locations_non_empty(tenant_client):
    conn = _tenant_conn()
    try:
        n = conn.execute("SELECT COUNT(*) FROM erp_locations").fetchone()[0]
    finally:
        conn.close()
    assert n > 0, "erp_locations is empty -> MWO creation would be blocked"


def test_distinct_roles_subset_canonical_no_technician(tenant_client):
    seen = set()
    conn = _tenant_conn()
    try:
        seen |= {r[0] for r in conn.execute("SELECT DISTINCT role FROM erp_employees").fetchall()}
    finally:
        conn.close()
    # The gateway is the only live store that carried TECHNICIAN; after the migration's
    # TECHNICIAN->TECH reconcile it must be canonical too.
    if os.path.exists(GATEWAY_DB_PATH):
        g = sqlite3.connect(GATEWAY_DB_PATH)
        try:
            seen |= {r[0] for r in g.execute("SELECT DISTINCT role FROM erp_employees").fetchall()}
        finally:
            g.close()
    assert "TECHNICIAN" not in seen, f"TECHNICIAN still present: {sorted(seen)}"
    assert seen <= CANONICAL, f"non-canonical roles present: {sorted(seen - CANONICAL)}"


def test_ingest_then_mwo_equipment_fk_boundary(tenant_client):
    as_user("ERP-1000", "ADMINISTRATOR")

    # (1) Canonical roles are seeded + registry-validated: ingest a TECH and an HM.
    r_tech = tenant_client.post(
        "/api/admin/ingest/single-user",
        json={"name": "Smoke Tech", "role": "TECH", "department_id": "DEPT-002"},
    )
    assert r_tech.status_code == 200, f"TECH ingest failed: {r_tech.status_code} {r_tech.text}"
    r_hm = tenant_client.post(
        "/api/admin/ingest/single-user",
        json={"name": "Smoke HM", "role": "HM", "department_id": "DEPT-002"},
    )
    assert r_hm.status_code == 200, f"HM ingest failed: {r_hm.status_code} {r_hm.text}"

    # (2) create_mwo on the seeded LOC-DEFAULT. location_id and created_by (ERP-1000)
    # FKs are satisfied; equipment_id is the ONLY unmet dependency, so the request must
    # get past role/auth + location validation and fail specifically on the equipment FK.
    r_mwo = tenant_client.post(
        "/api/mwo",
        json={
            "description": "Smoke WO",
            "equipment_id": "EQUIP-NOEXIST",   # deliberately absent -> sole possible FK failure
            "location_id": "LOC-DEFAULT",      # seeded -> location FK is satisfied
            "urgency": "Normal",
        },
    )
    # NOT a 403: role/auth passed (ADMINISTRATOR is authorized to create).
    assert r_mwo.status_code != 403, f"unexpected RBAC rejection: {r_mwo.text}"
    # create_mwo converts the sqlite FK IntegrityError to HTTP 500 with the DB message
    # in `detail` (maintenance_backend.py:2416-2419) -> the failure mode is an HTTP 500
    # referencing the foreign-key constraint, NOT a location/validation error.
    assert r_mwo.status_code == 500, f"expected FK-driven 500, got {r_mwo.status_code}: {r_mwo.text}"
    detail = (r_mwo.json() or {}).get("detail", "")
    assert "FOREIGN KEY" in detail.upper(), f"not the equipment FK failure mode: {detail!r}"
    assert "LOC" not in detail.upper(), f"location should be valid, not implicated: {detail!r}"
    # TODO(WS-A2): end-to-end MWO-create assertable once the equipment chain exists
    # under the capability model (WO scope resolves through equipment.department_id there).
