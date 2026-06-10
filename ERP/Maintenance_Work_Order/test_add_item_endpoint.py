"""
[BACK OFFICE INVENTORY MODULE] Manual Procurement Endpoint Verification.
Covers POST /api/orders/drafts/add-item: HOD RBAC, above-threshold procurement,
quantity accumulation, notes merging, supplier draft reuse, and input validation.
Same isolation pattern as test_inventory_module.py (temp DB copy + minted JWTs).

Execute: python test_add_item_endpoint.py
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

_tmpdir = tempfile.mkdtemp(prefix="additem_test_")
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

# Pre-condition: ensure no open admin-supplier draft skews the run (temp copy may carry one)
conn = db()
conn.execute("DELETE FROM erp_purchase_order_items WHERE po_id IN (SELECT po_id FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT')")
conn.execute("DELETE FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT'")
conn.commit()
sku = conn.execute("SELECT quantity_on_hand, reorder_threshold FROM erp_skus WHERE sku_id='SKU-ADM-003'").fetchone()
conn.close()

print("\n=== 1. RBAC Enforcement ===")
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["TECH"], json={"sku_id": "SKU-ADM-003", "quantity": 5})
check("TECH denied (403)", r.status_code == 403)
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["DM"], json={"sku_id": "SKU-ADM-003", "quantity": 5})
check("DM denied (403) - HOD-only capability", r.status_code == 403)

print("\n=== 2. Above-Threshold Manual Procurement ===")
check("precondition: SKU-ADM-003 stock above threshold", sku["quantity_on_hand"] > sku["reorder_threshold"],
      f"(stock={sku['quantity_on_hand']}, threshold={sku['reorder_threshold']})")
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["HM"],
                json={"sku_id": "SKU-ADM-003", "quantity": 15, "notes": "Quarterly toner stockpile"})
check("HM procurement accepted (201)", r.status_code == 201, str(r.json()) if r.status_code != 201 else "")
body = r.json()
check("new draft synthesized (created=true)", body.get("created") is True)
check("line quantity = 15", body.get("line_quantity") == 15)
po_id = body.get("po_id")

conn = db()
po = conn.execute("SELECT status, supplier_id, eta_date, notes FROM erp_purchase_orders WHERE po_id=?", (po_id,)).fetchone()
conn.close()
check("PO is DRAFT for designated supplier", po and po["status"] == "DRAFT" and po["supplier_id"] == "SUP-ADMIN-01")
check("ETA computed from supplier lead time", bool(po["eta_date"]))
check("notes persisted on new draft", po["notes"] == "Quarterly toner stockpile")

print("\n=== 3. Quantity Accumulation & Notes Merge ===")
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["HM"],
                json={"sku_id": "SKU-ADM-003", "quantity": 5, "notes": "Add 5 more"})
check("repeat add merged into same draft", r.json().get("po_id") == po_id and r.json().get("created") is False)
check("line quantity accumulated to 20", r.json().get("line_quantity") == 20)
conn = db()
notes = conn.execute("SELECT notes FROM erp_purchase_orders WHERE po_id=?", (po_id,)).fetchone()["notes"]
conn.close()
check("notes merged", notes == "Quarterly toner stockpile | Add 5 more")

print("\n=== 4. Supplier Draft Reuse Across SKUs ===")
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["HM"], json={"sku_id": "SKU-ADM-001", "quantity": 10})
check("second SKU lands on same supplier draft", r.json().get("po_id") == po_id)
conn = db()
n_items = conn.execute("SELECT COUNT(*) FROM erp_purchase_order_items WHERE po_id=?", (po_id,)).fetchone()[0]
n_drafts = conn.execute("SELECT COUNT(*) FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT'").fetchone()[0]
conn.close()
check("draft carries 2 line items", n_items == 2)
check("still exactly one DRAFT per supplier", n_drafts == 1)

r = client.get("/api/orders/drafts", headers=HEADERS["HM"])
match = [d for d in r.json()["data"] if d["po_id"] == po_id]
check("draft visible in HOD workspace feed with both items", match and len(match[0]["items"]) == 2)

print("\n=== 5. Input Validation ===")
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["HM"], json={"sku_id": "SKU-NONEXISTENT", "quantity": 5})
check("unknown SKU rejected (404)", r.status_code == 404)
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["HM"], json={"sku_id": "SKU-ADM-003", "quantity": 0})
check("zero quantity rejected (422)", r.status_code == 422)
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["HM"], json={"sku_id": "SKU-ADM-003", "quantity": -3})
check("negative quantity rejected (422)", r.status_code == 422)

print(f"\n{'='*50}\nRESULT: {_passed} passed, {_failed} failed")
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(1 if _failed else 0)
