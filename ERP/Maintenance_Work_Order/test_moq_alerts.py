"""
[BACK OFFICE INVENTORY MODULE] HM Safety Alerts & SKU MOQ Verification.
Covers: erp_skus.min_order_qty schema + seeds, GET /api/inventory/alerts
(RBAC, breach detection, draft PO linkage), MOQ round-up in the threshold
auto-draft worker, SKU ingestion with MOQ, and PO hydration exposure.
Same isolation pattern as test_inventory_module.py (temp DB copy + minted JWTs).

Execute: python test_moq_alerts.py
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

_tmpdir = tempfile.mkdtemp(prefix="moq_test_")
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

# Pre-condition: clear open admin-supplier drafts the temp copy may carry
conn = db()
conn.execute("DELETE FROM erp_purchase_order_items WHERE po_id IN (SELECT po_id FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT')")
conn.execute("DELETE FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT'")
# Normalize stock so no admin SKU starts breached
conn.execute("UPDATE erp_skus SET quantity_on_hand = reorder_threshold * 3 WHERE sku_id LIKE 'SKU-ADM-%'")
conn.commit()
conn.close()

print("\n=== 1. Schema & Seeds ===")
conn = db()
cols = {r["name"] for r in conn.execute("PRAGMA table_info(erp_skus)")}
check("erp_skus.min_order_qty column exists", "min_order_qty" in cols)
row = conn.execute("SELECT min_order_qty FROM erp_skus WHERE sku_id='SKU-ADM-001'").fetchone()
check("seed: copy paper MOQ = 5", row and row["min_order_qty"] == 5, f"got {row and row['min_order_qty']}")
row = conn.execute("SELECT min_order_qty FROM erp_skus WHERE sku_id='SKU-ADM-003'").fetchone()
check("seed: toner MOQ = 2", row and row["min_order_qty"] == 2, f"got {row and row['min_order_qty']}")
row = conn.execute("SELECT min_order_qty FROM erp_skus WHERE sku_id='SKU-ADM-002'").fetchone()
check("non-seeded SKU defaults to MOQ 1", row and (row["min_order_qty"] or 1) == 1)
conn.close()

print("\n=== 2. Alerts Endpoint RBAC ===")
r = client.get("/api/inventory/alerts", headers=HEADERS["TECH"])
check("TECH blocked from alerts (403)", r.status_code == 403, f"got {r.status_code}")
r = client.get("/api/inventory/alerts", headers=HEADERS["DM"])
check("DM blocked from alerts (403)", r.status_code == 403, f"got {r.status_code}")
r = client.get("/api/inventory/alerts", headers=HEADERS["HM"])
check("HM clearance accepted (200)", r.status_code == 200, f"got {r.status_code}")
check("envelope shape {status, data}", r.json().get("status") == "success" and isinstance(r.json().get("data"), list))

print("\n=== 3. Breach Detection ===")
baseline_ids = {a["sku_id"] for a in r.json()["data"]}
check("normalized admin SKUs not in alerts", not any(s.startswith("SKU-ADM-") for s in baseline_ids))

# Force a breach directly (no side-band worker involvement)
conn = db()
conn.execute("UPDATE erp_skus SET quantity_on_hand = 1 WHERE sku_id='SKU-ADM-002'")
conn.commit(); conn.close()
r = client.get("/api/inventory/alerts", headers=HEADERS["HM"])
alerts = {a["sku_id"]: a for a in r.json()["data"]}
check("breached SKU appears in alerts", "SKU-ADM-002" in alerts)
a = alerts.get("SKU-ADM-002", {})
check("alert carries stock + threshold + MOQ fields",
      {"quantity_on_hand", "reorder_threshold", "min_order_qty", "nomenclature"} <= set(a.keys()))
check("alert with no open draft has draft_po_id null", a.get("draft_po_id") is None)

print("\n=== 4. MOQ Round-Up in Auto-Draft Worker ===")
# Craft a SKU where the 2x-threshold heuristic (5) is BELOW the MOQ (20)
SKU = f"SKU-MOQ-{uuid.uuid4().hex[:6].upper()}"
r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json={
    "sku_id": SKU, "nomenclature": "MOQ Test Widget", "unit_cost": 3.50,
    "reorder_threshold": 5, "supplier_id": "SUP-ADMIN-01", "min_order_qty": 20,
})
check("SKU ingested with min_order_qty=20", r.status_code == 201, f"got {r.status_code}: {r.text[:120]}")
conn = db()
row = conn.execute("SELECT min_order_qty FROM erp_skus WHERE sku_id=?", (SKU,)).fetchone()
conn.close()
check("ingest persisted MOQ to erp_skus", row and row["min_order_qty"] == 20)

# Stock in 6 (above threshold), then out 1 -> on_hand 5 <= threshold 5 -> worker fires
r = client.post("/api/inventory/manual-log", headers=HEADERS["HM"],
                json={"sku_id": SKU, "direction": "IN", "quantity": 6, "comment": "moq test stock"})
check("stock-in accepted", r.status_code == 201, f"got {r.status_code}")
r = client.post("/api/inventory/manual-log", headers=HEADERS["HM"],
                json={"sku_id": SKU, "direction": "OUT", "quantity": 1, "comment": "moq test breach"})
check("stock-out accepted (triggers threshold worker)", r.status_code == 201, f"got {r.status_code}")

conn = db()
item = conn.execute("""
    SELECT i.po_id, i.quantity FROM erp_purchase_order_items i
    JOIN erp_purchase_orders po ON po.po_id = i.po_id
    WHERE i.sku_id = ? AND po.status = 'DRAFT'
""", (SKU,)).fetchone()
conn.close()
check("auto-draft created for breached SKU", item is not None)
# Heuristic alone would order 2*5-5 = 5; MOQ must round it up to 20
check("draft quantity rounded UP to MOQ (20, not 5)",
      item and item["quantity"] == 20, f"got {item and item['quantity']}")

print("\n=== 5. Draft Linkage & Hydration ===")
r = client.get("/api/inventory/alerts", headers=HEADERS["HM"])
alerts = {a["sku_id"]: a for a in r.json()["data"]}
check("breached SKU now linked to its draft PO",
      alerts.get(SKU, {}).get("draft_po_id") == (item and item["po_id"]),
      f"got {alerts.get(SKU, {}).get('draft_po_id')}")

r = client.get("/api/orders/drafts", headers=HEADERS["HM"])
check("drafts endpoint OK", r.status_code == 200)
items = [i for po in r.json()["data"] for i in po["items"] if i["sku_id"] == SKU]
check("hydrated PO line carries min_order_qty",
      items and items[0].get("min_order_qty") == 20, f"got {items and items[0].get('min_order_qty')}")

print("\n=== 6. Input Validation ===")
r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json={
    "sku_id": f"SKU-BAD-{uuid.uuid4().hex[:6]}", "nomenclature": "Bad MOQ", "unit_cost": 1.0,
    "reorder_threshold": 5, "supplier_id": "SUP-ADMIN-01", "min_order_qty": 0,
})
check("min_order_qty=0 rejected (422)", r.status_code == 422, f"got {r.status_code}")
r = client.post("/api/inventory/skus", headers=HEADERS["HM"], json={
    "sku_id": f"SKU-DEF-{uuid.uuid4().hex[:6].upper()}", "nomenclature": "Default MOQ", "unit_cost": 1.0,
    "reorder_threshold": 5, "supplier_id": "SUP-ADMIN-01",
})
check("omitted min_order_qty defaults to 1 (201)", r.status_code == 201, f"got {r.status_code}")

print("\n" + "=" * 50)
print(f"RESULT: {_passed} passed, {_failed} failed")
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(1 if _failed else 0)
