"""
[BACK OFFICE INVENTORY MODULE] Supplier Catalog & Inline SKU Ingestion Verification.
Covers: supplier registration validation (compulsory name/email, duplicates, optional
phone/address), supplier listing, HOD-extended SKU ingestion RBAC, and SKU-to-supplier
linkage. Same isolation pattern as the other suites (temp DB copy + minted JWTs).

Execute: python test_supplier_ingestion.py
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

_tmpdir = tempfile.mkdtemp(prefix="supplier_test_")
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
    "ADMIN": {"Authorization": f"Bearer {mint('ERP-1000', 'ADMIN')}"},
    "HM":    {"Authorization": f"Bearer {mint('ERP-2000', 'HM')}"},
    "TECH":  {"Authorization": f"Bearer {mint('ERP-3000', 'TECH')}"},
    "DM":    {"Authorization": f"Bearer {mint('ERP-4000', 'DM')}"},
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

# =====================================================================
print("\n=== 1. Supplier Schema Migration ===")
conn = db()
cols = {r[1] for r in conn.execute("PRAGMA table_info(erp_suppliers)")}
conn.close()
check("phone column present", "phone" in cols)
check("address column present", "address" in cols)

# =====================================================================
print("\n=== 2. Supplier Listing ===")
r = client.get("/api/inventory/suppliers", headers=HEADERS["HM"])
check("HM lists suppliers (200)", r.status_code == 200)
ids = {s["supplier_id"] for s in r.json()["data"]}
check("seed suppliers present", {"SUP-MAINT-01", "SUP-ADMIN-01"} <= ids)
check("payload exposes contact columns", all(k in r.json()["data"][0] for k in ("phone", "address", "default_lead_time_days")))

# =====================================================================
print("\n=== 3. Supplier Registration: RBAC ===")
valid_supplier = {"supplier_id": "SUP-TEST-99", "name": "Direct Parts Inc",
                  "email": "orders@directparts.example.com", "phone": "555-0142",
                  "address": "42 Industrial Way", "default_lead_time_days": 4}
r = client.post("/api/inventory/suppliers", headers=HEADERS["TECH"], json=valid_supplier)
check("TECH denied registration (403)", r.status_code == 403)
r = client.post("/api/inventory/suppliers", headers=HEADERS["DM"], json=valid_supplier)
check("DM denied registration (403)", r.status_code == 403)
r = client.post("/api/inventory/suppliers", headers=HEADERS["HM"], json=valid_supplier)
check("HM registration accepted (201)", r.status_code == 201, str(r.json()) if r.status_code != 201 else "")

conn = db()
row = conn.execute("SELECT * FROM erp_suppliers WHERE supplier_id='SUP-TEST-99'").fetchone()
conn.close()
check("supplier persisted with contact details", row and row["phone"] == "555-0142" and row["address"] == "42 Industrial Way")
check("lead time persisted", row["default_lead_time_days"] == 4)

# =====================================================================
print("\n=== 4. Supplier Registration: Validation ===")
r = client.post("/api/inventory/suppliers", headers=HEADERS["HM"], json=valid_supplier)
check("duplicate supplier_id rejected (409)", r.status_code == 409)
r = client.post("/api/inventory/suppliers", headers=HEADERS["HM"],
                json={"supplier_id": "SUP-BAD-01", "name": "X", "email": "ok@x.example.com"})
check("1-char name rejected (422)", r.status_code == 422)
r = client.post("/api/inventory/suppliers", headers=HEADERS["HM"],
                json={"supplier_id": "SUP-BAD-02", "name": "   ", "email": "ok@x.example.com"})
check("blank name rejected (422)", r.status_code == 422)
r = client.post("/api/inventory/suppliers", headers=HEADERS["HM"],
                json={"supplier_id": "SUP-BAD-03", "name": "No Email Co"})
check("missing email rejected (422)", r.status_code == 422)
r = client.post("/api/inventory/suppliers", headers=HEADERS["HM"],
                json={"supplier_id": "SUP-BAD-04", "name": "Bad Email Co", "email": "not-an-email"})
check("malformed email rejected (422)", r.status_code == 422)
r = client.post("/api/inventory/suppliers", headers=HEADERS["HM"],
                json={"supplier_id": "SUP-MIN-01", "name": "Minimal Co", "email": "min@co.example.com"})
check("minimal supplier (no phone/address) accepted, defaults applied", r.status_code == 201)
conn = db()
row = conn.execute("SELECT phone, address, default_lead_time_days FROM erp_suppliers WHERE supplier_id='SUP-MIN-01'").fetchone()
conn.close()
check("optional fields nullable + lead time defaults to 7",
      row["phone"] is None and row["address"] is None and row["default_lead_time_days"] == 7)

# =====================================================================
print("\n=== 5. SKU Ingestion: HOD Role Extension ===")
sku_payload = {"sku_id": "SKU-TEST-888", "nomenclature": "Testing Ingest Widget",
               "unit_cost": 12.50, "reorder_threshold": 5, "supplier_id": "SUP-TEST-99"}
r = client.post("/api/inventory/skus", headers=HEADERS["TECH"], json=sku_payload)
check("TECH denied SKU ingestion (403)", r.status_code == 403)
r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json=sku_payload)
check("HM SKU ingestion accepted (201) - role extension", r.status_code == 201, str(r.json()) if r.status_code != 201 else "")

conn = db()
row = conn.execute("SELECT supplier_id, unit_cost, reorder_threshold FROM erp_skus WHERE sku_id='SKU-TEST-888'").fetchone()
conn.close()
check("SKU linked to newly created supplier", row and row["supplier_id"] == "SUP-TEST-99")
check("SKU attributes persisted", row["unit_cost"] == 12.50 and row["reorder_threshold"] == 5)

r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json=sku_payload)
check("duplicate SKU rejected (409)", r.status_code == 409)
r = client.post("/api/inventory/skus", headers=HEADERS["HM"],
                json={**sku_payload, "sku_id": "SKU-TEST-889", "supplier_id": "SUP-GHOST-77"})
check("unregistered supplier rejected (400)", r.status_code == 400)
r = client.post("/api/inventory/skus", headers=HEADERS["ADMIN"],
                json={"sku_id": "SKU-TEST-890", "nomenclature": "Supplierless Widget", "unit_cost": 1.0, "reorder_threshold": 2})
check("supplier_id remains optional (ADMIN, 201)", r.status_code == 201)

# =====================================================================
print("\n=== 6. Inline Flow Chain (register supplier -> ingest SKU) ===")
r1 = client.post("/api/inventory/suppliers", headers=HEADERS["HM"],
                 json={"supplier_id": "SUP-INLINE-01", "name": "Inline Supplier Ltd",
                       "email": "sales@inline.example.com", "phone": "555-0199", "address": "123 Main St"})
r2 = client.post("/api/inventory/skus", headers=HEADERS["HM"],
                 json={"sku_id": "SKU-INLINE-01", "nomenclature": "Inline Chained Widget",
                       "unit_cost": 9.99, "reorder_threshold": 3, "supplier_id": "SUP-INLINE-01"})
check("chained registration + ingestion both succeed", r1.status_code == 201 and r2.status_code == 201)

# New supplier visible in directory; new SKU procurable via manual draft endpoint
r = client.get("/api/inventory/suppliers", headers=HEADERS["HM"])
check("inline supplier visible in directory", any(s["supplier_id"] == "SUP-INLINE-01" for s in r.json()["data"]))
r = client.post("/api/orders/drafts/add-item", headers=HEADERS["HM"], json={"sku_id": "SKU-INLINE-01", "quantity": 5})
check("new SKU procurable into supplier draft", r.status_code == 201 and r.json().get("created") is True)

print(f"\n{'='*50}\nRESULT: {_passed} passed, {_failed} failed")
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(1 if _failed else 0)
