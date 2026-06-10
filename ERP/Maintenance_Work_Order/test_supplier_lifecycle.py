"""
[BACK OFFICE INVENTORY MODULE] Supplier Lifecycle & Atomic Ingestion Verification.
Covers: atomic SKU+supplier ingestion (including rollback on failure — the orphan-supplier
fix), PUT supplier updates, SKU supplier reassignment, and supplier contact details
rendered into the approved-PO email. Same isolation pattern as the other suites.

Execute: python test_supplier_lifecycle.py
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

_tmpdir = tempfile.mkdtemp(prefix="lifecycle_test_")
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
    "CFO":  {"Authorization": f"Bearer {mint('ERP-5000', 'CFO')}"},
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

# Pre-condition: clear any open admin-supplier draft carried in the DB copy
conn = db()
conn.execute("DELETE FROM erp_purchase_order_items WHERE po_id IN (SELECT po_id FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT')")
conn.execute("DELETE FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT'")
conn.commit()
conn.close()

# =====================================================================
print("\n=== 1. Atomic SKU + Supplier Ingestion ===")
atomic_payload = {
    "sku_id": "SKU-ATOM-01", "nomenclature": "Atomic Test Widget",
    "unit_cost": 3.25, "reorder_threshold": 4,
    "new_supplier": {"supplier_id": "SUP-ATOM-01", "name": "Atomic Supplies Co",
                     "email": "orders@atomic.example.com", "phone": "555-0177",
                     "address": "1 Transaction Blvd", "default_lead_time_days": 5}
}
r = client.post("/api/inventory/skus", headers=HEADERS["TECH"], json=atomic_payload)
check("TECH denied atomic ingestion (403)", r.status_code == 403)
r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json=atomic_payload)
check("HM atomic ingestion accepted (201)", r.status_code == 201, str(r.json()) if r.status_code != 201 else "")
check("response flags supplier_created", r.json().get("supplier_created") is True and r.json().get("supplier_id") == "SUP-ATOM-01")

conn = db()
sup = conn.execute("SELECT phone, address FROM erp_suppliers WHERE supplier_id='SUP-ATOM-01'").fetchone()
sku = conn.execute("SELECT supplier_id FROM erp_skus WHERE sku_id='SKU-ATOM-01'").fetchone()
conn.close()
check("supplier persisted with contacts", sup and sup["phone"] == "555-0177")
check("SKU linked to embedded supplier", sku and sku["supplier_id"] == "SUP-ATOM-01")

# Rollback proof: duplicate SKU with a brand-new embedded supplier -> 409 AND no orphan supplier
r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json={
    **atomic_payload,
    "new_supplier": {"supplier_id": "SUP-ORPHAN-01", "name": "Orphan Risk Co", "email": "x@orphan.example.com"}
})
check("duplicate SKU rejected (409)", r.status_code == 409)
conn = db()
orphan = conn.execute("SELECT 1 FROM erp_suppliers WHERE supplier_id='SUP-ORPHAN-01'").fetchone()
conn.close()
check("embedded supplier rolled back (no orphan)", orphan is None)

r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json={
    **atomic_payload, "sku_id": "SKU-ATOM-02"
})
check("embedded duplicate supplier rejected (409)", r.status_code == 409)
conn = db()
sku2 = conn.execute("SELECT 1 FROM erp_skus WHERE sku_id='SKU-ATOM-02'").fetchone()
conn.close()
check("SKU rolled back when supplier conflicts", sku2 is None)

r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json={
    **atomic_payload, "sku_id": "SKU-ATOM-03",
    "new_supplier": {"supplier_id": "SUP-BADMAIL-01", "name": "Bad Mail Co", "email": "not-an-email"}
})
check("malformed embedded email rejected (422)", r.status_code == 422)

# =====================================================================
print("\n=== 2. Supplier Update (PUT) ===")
r = client.put("/api/inventory/suppliers/SUP-ADMIN-01", headers=HEADERS["TECH"], json={"phone": "555-0000"})
check("TECH denied update (403)", r.status_code == 403)
r = client.put("/api/inventory/suppliers/SUP-GHOST-77", headers=HEADERS["HM"], json={"phone": "555-0000"})
check("unknown supplier (404)", r.status_code == 404)
r = client.put("/api/inventory/suppliers/SUP-ADMIN-01", headers=HEADERS["HM"], json={})
check("empty mutation rejected (400)", r.status_code == 400)
r = client.put("/api/inventory/suppliers/SUP-ADMIN-01", headers=HEADERS["HM"], json={"email": "broken-email"})
check("malformed email rejected (422)", r.status_code == 422)
r = client.put("/api/inventory/suppliers/SUP-ADMIN-01", headers=HEADERS["HM"], json={"name": None})
check("nulling compulsory name rejected (422)", r.status_code == 422)
r = client.put("/api/inventory/suppliers/SUP-ADMIN-01", headers=HEADERS["HM"],
               json={"phone": "555-0123", "address": "77 OfficePro Plaza", "default_lead_time_days": 2})
check("contact + lead time update accepted", r.status_code == 200 and set(r.json()["updated_fields"]) == {"address", "default_lead_time_days", "phone"})
conn = db()
row = conn.execute("SELECT phone, address, default_lead_time_days, name FROM erp_suppliers WHERE supplier_id='SUP-ADMIN-01'").fetchone()
conn.close()
check("update persisted, untouched fields intact",
      row["phone"] == "555-0123" and row["address"] == "77 OfficePro Plaza"
      and row["default_lead_time_days"] == 2 and row["name"] == "OfficePro Supplies Ltd.")

# =====================================================================
print("\n=== 3. SKU Supplier Reassignment ===")
r = client.put("/api/inventory/skus/SKU-ADM-001/supplier", headers=HEADERS["TECH"], json={"supplier_id": "SUP-ATOM-01"})
check("TECH denied reassignment (403)", r.status_code == 403)
r = client.put("/api/inventory/skus/SKU-GHOST-99/supplier", headers=HEADERS["HM"], json={"supplier_id": "SUP-ATOM-01"})
check("unknown SKU (404)", r.status_code == 404)
r = client.put("/api/inventory/skus/SKU-ADM-001/supplier", headers=HEADERS["HM"], json={"supplier_id": "SUP-GHOST-77"})
check("unregistered target supplier (400)", r.status_code == 400)
r = client.put("/api/inventory/skus/SKU-ADM-001/supplier", headers=HEADERS["HM"], json={"supplier_id": "SUP-ATOM-01"})
check("reassignment accepted", r.status_code == 200)
r = client.get("/api/inventory/skus", headers=HEADERS["HM"])
row = next((s for s in r.json()["items"] if s["sku_id"] == "SKU-ADM-001"), None)
check("ledger feed reflects new supplier", row and row["supplier_name"] == "Atomic Supplies Co")
r = client.put("/api/inventory/skus/SKU-ADM-001/supplier", headers=HEADERS["HM"], json={"supplier_id": None})
conn = db()
val = conn.execute("SELECT supplier_id FROM erp_skus WHERE sku_id='SKU-ADM-001'").fetchone()["supplier_id"]
conn.close()
check("explicit null unassigns", r.status_code == 200 and val is None)
client.put("/api/inventory/skus/SKU-ADM-001/supplier", headers=HEADERS["HM"], json={"supplier_id": "SUP-ADMIN-01"})  # restore

# =====================================================================
print("\n=== 4. Supplier Contacts in Approved-PO Email ===")
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["HM"],
                json={"sku_id": "SKU-ADM-003", "quantity": 6, "notes": "Contact rendering check"})
po_id = r.json()["po_id"]
client.post("/api/orders/submit", headers=HEADERS["HM"], json={"po_id": po_id})
artifact = os.path.join(maintenance_backend.PO_EMAIL_LOG_DIR, f"{po_id}.html")
r = client.post("/api/orders/actuate-bulk", headers=HEADERS["CFO"], json={"po_ids": [po_id], "action": "APPROVE"})
check("PO approved by CFO", r.status_code == 200 and r.json()["results"][0]["result"] == "APPROVED")
check("email artifact rendered", os.path.exists(artifact))
if os.path.exists(artifact):
    with open(artifact, "r", encoding="utf-8") as f:
        html = f.read()
    check("email footer carries supplier phone", "555-0123" in html)
    check("email footer carries supplier address", "77 OfficePro Plaza" in html)
    os.remove(artifact)  # test artifact cleanup (live-probe discipline)

print(f"\n{'='*50}\nRESULT: {_passed} passed, {_failed} failed")
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(1 if _failed else 0)
