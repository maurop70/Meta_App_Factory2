"""
Verification for category-manager union gating, CSV report downloads, and CFO
notes actuation + email injection.

Exercises the real FastAPI route logic in-process via TestClient, overriding
verify_jwt_token so no RS256 gateway is required. Uses hermetic TEST- fixtures
and tears them down afterwards. Run: python test_reports_and_gating.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402
from jinja2 import Template  # noqa: E402
import maintenance_backend as mb  # noqa: E402
from local_db import get_db_connection  # noqa: E402

app = mb.app
client = TestClient(app)

_identity = {"payload": {"sub": "TEST-ADMIN", "role": "ADMIN", "jti": "test"}}


def _fake_auth():
    return _identity["payload"]


app.dependency_overrides[mb.verify_jwt_token] = _fake_auth


def as_user(sub, role):
    _identity["payload"] = {"sub": sub, "role": role, "jti": "test"}


# --- Fixtures ---
CAT = "TEST-CAT-RG"
SUP = "TEST-SUP-RG"
SKU_IN = "TEST-SKU-IN"      # belongs to the managed category
SKU_OUT = "TEST-SKU-OUT"    # no category, no clearance
DM_MGR = "TEST-DM-MGR"      # DM, manages CAT (no explicit clearances)
DM_NONE = "TEST-DM-NONE"    # DM, manages nothing, no clearances
PO = "TEST-PO-RG"
CFO_NOTE = "EXPEDITE-RG-SHIPMENT"


def seed():
    conn = get_db_connection()
    try:
        # Employees first: erp_categories.manager_id has an FK to erp_employees(id).
        for emp in (DM_MGR, DM_NONE):
            conn.execute("INSERT OR REPLACE INTO erp_employees (id, name, role, pin_hash, is_active) VALUES (?, ?, 'DM', 'x', 1)", (emp, emp))
        conn.execute("INSERT OR REPLACE INTO erp_categories (id, name, manager_id) VALUES (?, 'RG Test Cat', ?)", (CAT, DM_MGR))
        conn.execute("INSERT OR REPLACE INTO erp_suppliers (supplier_id, name, email, phone, address, default_lead_time_days) "
                     "VALUES (?, 'RG Supplier', 'rg@test.local', '555', 'Addr', 5)", (SUP,))
        conn.execute("INSERT OR REPLACE INTO erp_skus (sku_id, nomenclature, unit_cost, reorder_threshold, quantity_on_hand, supplier_id, category_id, min_order_qty) "
                     "VALUES (?, 'In-Category Part', 2.5, 10, 3, ?, ?, 1)", (SKU_IN, SUP, CAT))
        conn.execute("INSERT OR REPLACE INTO erp_skus (sku_id, nomenclature, unit_cost, reorder_threshold, quantity_on_hand, supplier_id, category_id, min_order_qty) "
                     "VALUES (?, 'Out-Category Part', 2.5, 10, 3, ?, NULL, 1)", (SKU_OUT, SUP))
        conn.execute("INSERT OR REPLACE INTO erp_purchase_orders (po_id, supplier_id, status, priority, notes) "
                     "VALUES (?, ?, 'PENDING_CFO', 0, 'HOD requested expedite')", (PO, SUP))
        conn.execute("INSERT OR REPLACE INTO erp_purchase_order_items (po_id, sku_id, quantity, unit_cost) VALUES (?, ?, 2, 2.5)", (PO, SKU_IN))
        conn.commit()
    finally:
        conn.close()


def cleanup():
    conn = get_db_connection()
    try:
        # All POs for the test supplier (drafts created via add-item + the seeded PO).
        po_ids = [r["po_id"] for r in conn.execute(
            "SELECT po_id FROM erp_purchase_orders WHERE supplier_id = ?", (SUP,)).fetchall()]
        for po in po_ids:
            conn.execute("DELETE FROM erp_purchase_order_items WHERE po_id = ?", (po,))
            conn.execute("DELETE FROM erp_purchase_orders WHERE po_id = ?", (po,))
        conn.execute("DELETE FROM erp_employee_sku_access WHERE employee_id IN (?, ?)", (DM_MGR, DM_NONE))
        # Order respects FKs: skus -> category(manager_id->employees) -> employees.
        conn.execute("DELETE FROM erp_skus WHERE sku_id IN (?, ?)", (SKU_IN, SKU_OUT))
        conn.execute("DELETE FROM erp_categories WHERE id = ?", (CAT,))
        conn.execute("DELETE FROM erp_employees WHERE id IN (?, ?)", (DM_MGR, DM_NONE))
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
    print("== Category-Manager Union Gating ==")
    # A DM who manages a category sees its SKUs via the union, with no explicit clearances.
    as_user(DM_MGR, "DM")
    r = client.get("/api/inventory/skus")
    check("category-manager DM GET /inventory/skus -> 200", r.status_code == 200)
    skus = {s["sku_id"] for s in r.json().get("items", [])}
    check("manager sees in-category SKU via union", SKU_IN in skus)
    check("manager does NOT see out-of-category SKU", SKU_OUT not in skus)

    # verify_employee_sku_access: category grants access; non-category SKU is denied.
    r = client.post("/api/orders/drafts/add-item", json={"sku_id": SKU_IN, "quantity": 2})
    check("manager add-item in-category SKU -> 201", r.status_code == 201)
    r = client.post("/api/orders/drafts/add-item", json={"sku_id": SKU_OUT, "quantity": 2})
    check("manager add-item out-of-category SKU -> 403", r.status_code == 403)

    # A DM with neither a managed category nor explicit clearances is locked out.
    as_user(DM_NONE, "DM")
    r = client.get("/api/inventory/skus")
    check("unmapped DM GET /inventory/skus -> 403", r.status_code == 403)

    print("== CSV Report Downloads ==")
    as_user("TEST-ADMIN", "ADMIN")
    r = client.get("/api/reports/inventory/download")
    check("admin inventory CSV -> 200", r.status_code == 200)
    check("inventory CSV content-type is text/csv", r.headers.get("content-type", "").startswith("text/csv"))
    check("inventory CSV has UTF-8 BOM", r.content[:3] == b"\xef\xbb\xbf")
    check("inventory CSV has header + seeded SKU", "Nomenclature" in r.text and SKU_IN in r.text)

    as_user("TEST-CFO", "CFO")
    r = client.get("/api/reports/cfo-procurement/download")
    check("CFO procurement CSV -> 200", r.status_code == 200)
    check("CFO procurement CSV lists seeded PO", PO in r.text)
    as_user(DM_NONE, "TECH")
    r = client.get("/api/reports/cfo-procurement/download")
    check("TECH cfo-procurement CSV -> 403", r.status_code == 403)

    as_user(DM_MGR, "DM")
    r = client.get("/api/reports/dm-work-orders/download")
    check("DM work-orders CSV -> 200", r.status_code == 200)
    as_user("TEST-TECH", "TECH")
    r = client.get("/api/reports/dm-work-orders/download")
    check("TECH dm-work-orders CSV -> 403", r.status_code == 403)

    as_user("TEST-HM", "HM")
    r = client.get("/api/reports/hm-work-orders/download")
    check("HM work-orders CSV -> 200", r.status_code == 200)
    as_user(DM_MGR, "DM")
    r = client.get("/api/reports/hm-work-orders/download")
    check("DM hm-work-orders CSV -> 403", r.status_code == 403)

    print("== CFO Notes Actuation + Email Injection ==")
    as_user("TEST-CFO", "CFO")
    r = client.post("/api/orders/actuate-bulk", json={"po_ids": [PO], "action": "APPROVE", "cfo_notes": CFO_NOTE})
    check("CFO actuate-bulk APPROVE with notes -> 200", r.status_code == 200)

    conn = get_db_connection()
    try:
        row = conn.execute("SELECT status, cfo_notes FROM erp_purchase_orders WHERE po_id = ?", (PO,)).fetchone()
        check("PO persisted status APPROVED", row and row["status"] == "APPROVED")
        check("PO persisted cfo_notes", row and row["cfo_notes"] == CFO_NOTE)
        hydrated = [p for p in mb._hydrate_purchase_orders(conn, ["APPROVED"]) if p["po_id"] == PO]
        check("hydration exposes cfo_notes", hydrated and hydrated[0].get("cfo_notes") == CFO_NOTE)
    finally:
        conn.close()

    # Email template injection: the rendered HTML must carry the CFO notes block.
    with open(mb.PO_EMAIL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        tpl = Template(f.read())
    html = tpl.render(po=hydrated[0], generated_at="test-run")
    check("email HTML injects cfo_notes", CFO_NOTE in html)
    check("email HTML still renders HOD notes", "HOD requested expedite" in html)


if __name__ == "__main__":
    try:
        cleanup()
        seed()
        run()
    finally:
        cleanup()
    print(f"\n== {PASS} passed, {FAIL} failed ==")
    sys.exit(1 if FAIL else 0)
