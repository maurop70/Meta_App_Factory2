"""
Restricted-SKU procurement verification.

Exercises the real FastAPI route logic in-process via TestClient, overriding
verify_jwt_token so no RS256 gateway is required. Uses hermetic TEST- fixtures
and tears them down afterwards. Run: python test_employee_sku_access.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402
import maintenance_backend as mb  # noqa: E402
from local_db import get_db_connection  # noqa: E402

app = mb.app
# No context manager -> lifespan (gateway public-key fetch) is not triggered.
client = TestClient(app)

# --- Auth override: inject an arbitrary identity per call ---
_identity = {"payload": {"sub": "TEST-ADMIN", "role": "ADMIN", "jti": "test"}}


def _fake_auth():
    return _identity["payload"]


app.dependency_overrides[mb.verify_jwt_token] = _fake_auth


def as_user(sub, role):
    _identity["payload"] = {"sub": sub, "role": role, "jti": "test"}


# --- Fixtures ---
SUP = "TEST-SUP-1"
SKU1 = "TEST-SKU-BOLT-M8"   # will be granted to the tech
SKU2 = "TEST-SKU-NUT-M8"    # never granted to the tech
TECH = "TEST-TECH-1001"     # restricted user, gets SKU1
TECH2 = "TEST-TECH-2002"    # restricted user, no clearances


def seed():
    conn = get_db_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO erp_suppliers (supplier_id, name, email, phone, address, default_lead_time_days) "
                     "VALUES (?, 'Test Supplier', 'sup@test.local', '555', 'Addr', 5)", (SUP,))
        for sku, nom in [(SKU1, "Bolt M8"), (SKU2, "Nut M8")]:
            conn.execute("INSERT OR REPLACE INTO erp_skus (sku_id, nomenclature, unit_cost, reorder_threshold, quantity_on_hand, supplier_id, min_order_qty) "
                         "VALUES (?, ?, 2.5, 10, 3, ?, 1)", (sku, nom, SUP))
        for emp in (TECH, TECH2):
            conn.execute("INSERT OR REPLACE INTO erp_employees (id, name, role, pin_hash, is_active) "
                         "VALUES (?, ?, 'TECH', 'x', 1)", (emp, emp))
        conn.commit()
    finally:
        conn.close()


def cleanup():
    conn = get_db_connection()
    try:
        # Drop any draft POs for the test supplier (cascade clears items).
        po_ids = [r["po_id"] for r in conn.execute(
            "SELECT po_id FROM erp_purchase_orders WHERE supplier_id = ?", (SUP,)).fetchall()]
        for po in po_ids:
            conn.execute("DELETE FROM erp_purchase_order_items WHERE po_id = ?", (po,))
            conn.execute("DELETE FROM erp_purchase_orders WHERE po_id = ?", (po,))
        conn.execute("DELETE FROM erp_employee_sku_access WHERE employee_id IN (?, ?)", (TECH, TECH2))
        conn.execute("DELETE FROM erp_skus WHERE sku_id IN (?, ?)", (SKU1, SKU2))
        conn.execute("DELETE FROM erp_employees WHERE id IN (?, ?)", (TECH, TECH2))
        conn.execute("DELETE FROM erp_suppliers WHERE supplier_id = ?", (SUP,))
        conn.commit()
    finally:
        conn.close()


PASS, FAIL = 0, 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


def run():
    print("== Restricted SKU Procurement Verification ==")

    # 1. Admin assigns SKU1 to the tech.
    as_user("TEST-ADMIN", "ADMIN")
    r = client.get(f"/api/admin/users/{TECH}/skus")
    check("admin GET skus -> 200", r.status_code == 200)
    body = r.json()
    check("tech starts with no assigned SKUs", body["assigned"] == [])
    check("both test SKUs are available", {SKU1, SKU2} <= {s["sku_id"] for s in body["available"]})

    r = client.post(f"/api/admin/users/{TECH}/skus", json={"sku_id": SKU1})
    check("admin assign SKU1 -> 201", r.status_code == 201)

    r = client.get(f"/api/admin/users/{TECH}/skus")
    check("SKU1 now assigned", SKU1 in {s["sku_id"] for s in r.json()["assigned"]})

    # 2. Restricted tech sees only the mapped SKU.
    as_user(TECH, "TECH")
    r = client.get("/api/inventory/skus")
    check("tech GET /inventory/skus -> 200", r.status_code == 200)
    skus = {s["sku_id"] for s in r.json()["items"]}
    check("tech sees only SKU1", SKU1 in skus and SKU2 not in skus)

    # 3. Adding an unassigned SKU is forbidden.
    r = client.post("/api/orders/drafts/add-item", json={"sku_id": SKU2, "quantity": 4})
    check("tech add-item unassigned SKU2 -> 403", r.status_code == 403)

    # 4. Adding an assigned SKU succeeds.
    r = client.post("/api/orders/drafts/add-item", json={"sku_id": SKU1, "quantity": 4})
    check("tech add-item assigned SKU1 -> 201", r.status_code == 201)

    # 5. A restricted tech with no clearances is locked out entirely.
    as_user(TECH2, "TECH")
    r = client.get("/api/inventory/skus")
    check("unmapped tech GET /inventory/skus -> 403", r.status_code == 403)

    # 6. Admin issues a draft on behalf of the tech.
    as_user("TEST-ADMIN", "ADMIN")
    r = client.post(f"/api/admin/users/{TECH}/orders/drafts/add-item", json={"sku_id": SKU1, "quantity": 2})
    check("admin on-behalf assigned SKU1 -> 201", r.status_code == 201)
    r = client.post(f"/api/admin/users/{TECH}/orders/drafts/add-item", json={"sku_id": SKU2, "quantity": 2})
    check("admin on-behalf unassigned SKU2 -> 403", r.status_code == 403)

    # 7. Draft list is redacted to cleared SKUs for the tech.
    as_user(TECH, "TECH")
    r = client.get("/api/orders/drafts")
    check("tech GET /orders/drafts -> 200", r.status_code == 200)
    drafts = r.json()["data"]
    leaked = [it["sku_id"] for po in drafts for it in po["items"] if it["sku_id"] != SKU1]
    check("draft view contains no foreign line items", leaked == [])

    # 8. Revoke restores empty clearance.
    as_user("TEST-ADMIN", "ADMIN")
    r = client.delete(f"/api/admin/users/{TECH}/skus/{SKU1}")
    check("admin revoke SKU1 -> 204", r.status_code == 204)
    r = client.get(f"/api/admin/users/{TECH}/skus")
    check("tech assignments empty after revoke", r.json()["assigned"] == [])


if __name__ == "__main__":
    try:
        cleanup()  # clear any stale state from a prior aborted run
        seed()
        run()
    finally:
        cleanup()
    print(f"\n== {PASS} passed, {FAIL} failed ==")
    sys.exit(1 if FAIL else 0)
