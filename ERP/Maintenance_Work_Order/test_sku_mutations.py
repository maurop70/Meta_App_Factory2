"""
[BACK OFFICE INVENTORY MODULE] SKU Mutation Endpoint Verification.
Covers PUT /api/inventory/skus/{sku_id}: HOD RBAC, partial updates, supplier
validation/clearing, bounds validation, unknown-field tolerance (frontend
reuses the POST payload), and MOQ updates feeding the threshold worker.
Same isolation pattern as test_inventory_module.py (temp DB copy + minted JWTs).

Execute: python test_sku_mutations.py
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid

import jwt as pyjwt

_here = os.path.dirname(os.path.abspath(__file__))
SOURCE_DB = os.path.join(_here, "data", "maintenance_erp.db")
PRIVATE_KEY_PATH = os.path.join(os.path.dirname(_here), "Module_0_Gateway", "keys", "private_key.pem")

_tmpdir = tempfile.mkdtemp(prefix="skumut_test_")
TEST_DB = os.path.join(_tmpdir, "maintenance_erp.db")
shutil.copy2(SOURCE_DB, TEST_DB)

import local_db
local_db.DB_PATH = TEST_DB

import maintenance_backend
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization

with open(PRIVATE_KEY_PATH, "r") as f:
    PRIVATE_KEY = f.read()
_private = serialization.load_pem_private_key(PRIVATE_KEY.encode(), password=None)
maintenance_backend.PUBLIC_KEY = _private.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

client = TestClient(maintenance_backend.app)

def mint(sub, role):
    return pyjwt.encode(
        {"sub": sub, "role": role, "exp": int(time.time()) + 3600, "jti": str(uuid.uuid4())},
        PRIVATE_KEY, algorithm="RS256"
    )

HEADERS = {
    "HM":   {"Authorization": f"Bearer {mint('ERP-2000', 'HM')}"},
    "TECH": {"Authorization": f"Bearer {mint('ERP-3000', 'TECH')}"},
    "DM":   {"Authorization": f"Bearer {mint('ERP-4000', 'DM')}"},
}

_passed, _failed = 0, 0

def check(label, condition, detail=""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {label}")
    else:
        _failed += 1
        print(f"  [FAIL] {label} {detail}")

def db():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn

def sku_row(sku_id):
    conn = db()
    row = conn.execute("SELECT * FROM erp_skus WHERE sku_id=?", (sku_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# Pre-condition: clear open admin drafts; create a dedicated mutation target
conn = db()
conn.execute("DELETE FROM erp_purchase_order_items WHERE po_id IN (SELECT po_id FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT')")
conn.execute("DELETE FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT'")
conn.commit(); conn.close()

SKU = f"SKU-MUT-{uuid.uuid4().hex[:6].upper()}"
r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json={
    "sku_id": SKU, "nomenclature": "Mutation Target", "unit_cost": 10.0,
    "reorder_threshold": 5, "supplier_id": "SUP-ADMIN-01", "min_order_qty": 2,
})
assert r.status_code == 201, f"fixture SKU creation failed: {r.text}"

print("\n=== 1. RBAC & Existence ===")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["TECH"], json={"min_order_qty": 9})
check("TECH blocked (403)", r.status_code == 403, f"got {r.status_code}")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["DM"], json={"min_order_qty": 9})
check("DM blocked (403)", r.status_code == 403, f"got {r.status_code}")
r = client.put("/api/inventory/skus/SKU-DOES-NOT-EXIST", headers=HEADERS["HM"], json={"min_order_qty": 9})
check("unknown SKU rejected (404)", r.status_code == 404, f"got {r.status_code}")
check("TECH attempt left record untouched", sku_row(SKU)["min_order_qty"] == 2)

print("\n=== 2. Partial Updates ===")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={"min_order_qty": 12})
check("MOQ-only update accepted (200)", r.status_code == 200, f"got {r.status_code}")
row = sku_row(SKU)
check("MOQ persisted", row["min_order_qty"] == 12, f"got {row['min_order_qty']}")
check("untouched fields preserved", row["nomenclature"] == "Mutation Target"
      and row["unit_cost"] == 10.0 and row["reorder_threshold"] == 5)

r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={
    "nomenclature": "Mutation Target v2", "unit_cost": 12.75, "reorder_threshold": 8})
check("multi-field update accepted", r.status_code == 200)
row = sku_row(SKU)
check("multi-field values persisted", row["nomenclature"] == "Mutation Target v2"
      and row["unit_cost"] == 12.75 and row["reorder_threshold"] == 8)
check("MOQ untouched by other-field update", row["min_order_qty"] == 12)

print("\n=== 3. Supplier Mutation ===")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={"supplier_id": "SUP-NOPE-99"})
check("unknown supplier rejected (400)", r.status_code == 400, f"got {r.status_code}")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={"supplier_id": "SUP-MAINT-01"})
check("supplier reassignment accepted", r.status_code == 200)
check("supplier persisted", sku_row(SKU)["supplier_id"] == "SUP-MAINT-01")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={"supplier_id": None})
check("explicit null clears supplier (200)", r.status_code == 200, f"got {r.status_code}")
check("supplier cleared in DB", sku_row(SKU)["supplier_id"] is None)

print("\n=== 4. Bounds & Payload Tolerance ===")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={"min_order_qty": 0})
check("min_order_qty=0 rejected (422)", r.status_code == 422, f"got {r.status_code}")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={"unit_cost": -4.0})
check("negative unit_cost rejected (422)", r.status_code == 422, f"got {r.status_code}")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={"reorder_threshold": -1})
check("negative reorder_threshold rejected (422)", r.status_code == 422, f"got {r.status_code}")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={})
check("empty payload is a clean no-op (200)", r.status_code == 200, f"got {r.status_code}")
# The edit modal reuses the POST payload shape: sku_id + new_supplier ride along
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={
    "sku_id": SKU, "nomenclature": "Mutation Target v3", "unit_cost": 13.0,
    "reorder_threshold": 8, "min_order_qty": 12, "supplier_id": "SUP-ADMIN-01",
    "new_supplier": None})
check("frontend-shaped payload tolerated (200)", r.status_code == 200, f"got {r.status_code}")
check("frontend-shaped payload persisted", sku_row(SKU)["nomenclature"] == "Mutation Target v3")

print("\n=== 5. Updated MOQ Drives Threshold Worker ===")
r = client.put(f"/api/inventory/skus/{SKU}", headers=HEADERS["HM"], json={"min_order_qty": 30})
check("MOQ raised to 30", r.status_code == 200)
# threshold 8: stock to 9, breach to 8 -> heuristic 2*8-8=8 < 30 -> expect 30
r = client.post("/api/inventory/manual-log", headers=HEADERS["HM"],
                json={"sku_id": SKU, "direction": "IN", "quantity": 9, "comment": "mut test stock"})
check("stock-in accepted", r.status_code == 201, f"got {r.status_code}")
r = client.post("/api/inventory/manual-log", headers=HEADERS["HM"],
                json={"sku_id": SKU, "direction": "OUT", "quantity": 1, "comment": "mut test breach"})
check("stock-out accepted", r.status_code == 201, f"got {r.status_code}")
conn = db()
item = conn.execute("""
    SELECT i.quantity FROM erp_purchase_order_items i
    JOIN erp_purchase_orders po ON po.po_id = i.po_id
    WHERE i.sku_id = ? AND po.status = 'DRAFT'
""", (SKU,)).fetchone()
conn.close()
check("auto-draft uses the UPDATED MOQ (30)", item and item["quantity"] == 30,
      f"got {item and item['quantity']}")

print("\n=== 6. Ledger Exposure ===")
# Endpoint enforces strict pagination (limit <= 100, CLAUDE_RULES 3.3) — page through
listed, list_ok, offset = None, True, 0
while listed is None:
    r = client.get(f"/api/inventory/skus?limit=100&offset={offset}", headers=HEADERS["HM"])
    if r.status_code != 200:
        list_ok = False
        break
    items = r.json().get("items", [])
    listed = next((s for s in items if s["sku_id"] == SKU), None)
    offset += 100
    if not items or offset > r.json().get("total", 0):
        break
check("skus list OK (paginated)", list_ok)
check("list exposes min_order_qty for the modal",
      listed is not None and listed.get("min_order_qty") == 30,
      f"got {listed and listed.get('min_order_qty')}")

print("\n=== 7. Update Triggers Auto-Draft ===")
# Create a SKU that is below threshold (qty 3, threshold 10) but lacks a supplier
SKU_ALERT = f"SKU-ALERT-{uuid.uuid4().hex[:6].upper()}"
r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json={
    "sku_id": SKU_ALERT, "nomenclature": "Alert Trigger Test Widget", "unit_cost": 2.50,
    "reorder_threshold": 10, "supplier_id": None, "min_order_qty": 5,
})
check("SKU created without supplier", r.status_code == 201)

# Set its quantity below threshold manually
conn = db()
conn.execute("UPDATE erp_skus SET quantity_on_hand = 3 WHERE sku_id = ?", (SKU_ALERT,))
conn.commit()
conn.close()

# Verify that it shows in alerts but with no draft PO
r = client.get("/api/inventory/alerts", headers=HEADERS["HM"])
alerts = {a["sku_id"]: a for a in r.json().get("data", [])}
check("breached SKU in alerts", SKU_ALERT in alerts)
check("draft_po_id is None initially", alerts[SKU_ALERT].get("draft_po_id") is None)

# Update SKU to assign a supplier (which should run background threshold evaluator)
r = client.put(f"/api/inventory/skus/{SKU_ALERT}", headers=HEADERS["HM"], json={
    "supplier_id": "SUP-ADMIN-01"
})
check("update SKU to assign supplier accepted", r.status_code == 200)

# Verify that draft PO was synthesized and linked
r = client.get("/api/inventory/alerts", headers=HEADERS["HM"])
alerts = {a["sku_id"]: a for a in r.json().get("data", [])}
check("draft_po_id is now populated after update", alerts[SKU_ALERT].get("draft_po_id") is not None)

print("\n" + "=" * 50)
print(f"RESULT: {_passed} passed, {_failed} failed")
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(1 if _failed else 0)

