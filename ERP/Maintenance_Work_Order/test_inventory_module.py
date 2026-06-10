"""
[BACK OFFICE INVENTORY MODULE] Verification Suite.
Runs against an isolated temp copy of maintenance_erp.db with locally minted RS256 JWTs
(no gateway required). Covers: migration integrity, manual log mutation, threshold
auto-drafting, HOD draft mutations, CFO RBAC enforcement, approval email artifact,
and shipment receipt inventory synchronization.

Execute: python test_inventory_module.py
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

# --- Isolate database BEFORE importing the backend ---
_tmpdir = tempfile.mkdtemp(prefix="inv_test_")
TEST_DB = os.path.join(_tmpdir, "maintenance_erp.db")
shutil.copy2(SOURCE_DB, TEST_DB)

import local_db
local_db.DB_PATH = TEST_DB

import maintenance_backend
from fastapi.testclient import TestClient

# --- Mint matching RS256 keypair tokens (bypasses the gateway lifespan fetch) ---
with open(PRIVATE_KEY_PATH, "r") as f:
    PRIVATE_KEY = f.read()

from cryptography.hazmat.primitives import serialization
_private = serialization.load_pem_private_key(PRIVATE_KEY.encode(), password=None)
PUBLIC_KEY = _private.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()
maintenance_backend.PUBLIC_KEY = PUBLIC_KEY

client = TestClient(maintenance_backend.app)  # no context manager: lifespan suppressed

def mint(sub, role):
    return pyjwt.encode(
        {"sub": sub, "role": role, "exp": int(time.time()) + 3600, "jti": str(uuid.uuid4())},
        PRIVATE_KEY, algorithm="RS256"
    )

HEADERS = {
    "ADMIN": {"Authorization": f"Bearer {mint('ERP-1000', 'ADMIN')}"},
    "HM":    {"Authorization": f"Bearer {mint('ERP-2000', 'HM')}"},
    "TECH":  {"Authorization": f"Bearer {mint('ERP-3000', 'TECH')}"},
    "CFO":   {"Authorization": f"Bearer {mint('ERP-5000', 'CFO')}"},
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
print("\n=== 1. Migration Integrity ===")
conn = db()
tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
for t in ["erp_suppliers", "erp_purchase_orders", "erp_purchase_order_items", "erp_inventory_manual_logs"]:
    check(f"table {t} exists", t in tables)
check("seed suppliers present",
      conn.execute("SELECT COUNT(*) FROM erp_suppliers WHERE supplier_id IN ('SUP-MAINT-01','SUP-ADMIN-01')").fetchone()[0] == 2)
check("admin SKUs classified under CAT-ADMIN",
      conn.execute("SELECT COUNT(*) FROM erp_skus WHERE category_id = 'CAT-ADMIN'").fetchone()[0] >= 4)
check("erp_employees admits CFO role",
      "'CFO'" in conn.execute("SELECT sql FROM sqlite_master WHERE name='erp_employees'").fetchone()[0])
check("CFO operator seeded",
      conn.execute("SELECT role FROM erp_employees WHERE id='ERP-5000'").fetchone()[0] == "CFO")
conn.close()

# =====================================================================
print("\n=== 2. Manual Log Ingestion (Stock-In / Stock-Out) ===")
conn = db()
qty_before = conn.execute("SELECT quantity_on_hand FROM erp_skus WHERE sku_id='SKU-ADM-001'").fetchone()[0]
conn.close()

r = client.post("/api/inventory/manual-log", headers=HEADERS["ADMIN"],
                json={"sku_id": "SKU-ADM-001", "direction": "IN", "quantity": 5, "comment": "cycle count correction"})
check("stock-in returns 201", r.status_code == 201, str(r.json()) if r.status_code != 201 else "")
check("stock-in increments quantity", r.json().get("new_quantity_on_hand") == qty_before + 5)

r = client.post("/api/inventory/manual-log", headers=HEADERS["ADMIN"],
                json={"sku_id": "SKU-ADM-001", "direction": "OUT", "quantity": 5, "comment": "damaged parts write-off"})
check("stock-out decrements quantity", r.status_code == 201 and r.json()["new_quantity_on_hand"] == qty_before)

r = client.post("/api/inventory/manual-log", headers=HEADERS["ADMIN"],
                json={"sku_id": "SKU-ADM-001", "direction": "OUT", "quantity": 999999})
check("stock-out exceeding on-hand rejected (400)", r.status_code == 400)

r = client.post("/api/inventory/manual-log", headers=HEADERS["ADMIN"],
                json={"sku_id": "SKU-NONEXISTENT", "direction": "OUT", "quantity": 1})
check("unknown SKU rejected (404)", r.status_code == 404)

conn = db()
log = conn.execute("SELECT direction, quantity, comment, logged_by FROM erp_inventory_manual_logs ORDER BY log_id DESC LIMIT 2").fetchall()
conn.close()
check("zero-trust log captured operator identity", any(l["logged_by"] == "ERP-1000" for l in log))
check("zero-trust log captured reasoning", any(l["comment"] == "damaged parts write-off" for l in log))

# =====================================================================
print("\n=== 3. Threshold Breach Auto-Drafting ===")
conn = db()
sku = conn.execute("SELECT quantity_on_hand, reorder_threshold FROM erp_skus WHERE sku_id='SKU-ADM-003'").fetchone()
conn.close()
breach_qty = sku["quantity_on_hand"] - sku["reorder_threshold"] + 1  # drop to threshold - 1
r = client.post("/api/inventory/manual-log", headers=HEADERS["ADMIN"],
                json={"sku_id": "SKU-ADM-003", "direction": "OUT", "quantity": breach_qty, "comment": "toner consumed"})
check("breaching stock-out accepted", r.status_code == 201)

conn = db()
po = conn.execute("SELECT po_id, status, supplier_id, eta_date FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT'").fetchone()
check("DRAFT PO auto-synthesized for designated supplier", po is not None)
if po:
    item = conn.execute("SELECT quantity, unit_cost FROM erp_purchase_order_items WHERE po_id=? AND sku_id='SKU-ADM-003'", (po["po_id"],)).fetchone()
    check("breached SKU present as line item", item is not None)
    check("ETA pre-computed from supplier lead time", bool(po["eta_date"]))
draft_po_id = po["po_id"] if po else None
conn.close()

# Second SKU, same supplier -> appends to the existing draft (no duplicate PO)
conn = db()
sku = conn.execute("SELECT quantity_on_hand, reorder_threshold FROM erp_skus WHERE sku_id='SKU-ADM-002'").fetchone()
conn.close()
breach_qty = sku["quantity_on_hand"] - sku["reorder_threshold"] + 1
client.post("/api/inventory/manual-log", headers=HEADERS["ADMIN"],
            json={"sku_id": "SKU-ADM-002", "direction": "OUT", "quantity": breach_qty, "comment": "pens depleted"})
conn = db()
check("second breach appended to same draft (one DRAFT per supplier)",
      conn.execute("SELECT COUNT(*) FROM erp_purchase_orders WHERE supplier_id='SUP-ADMIN-01' AND status='DRAFT'").fetchone()[0] == 1)
check("draft now carries 2 line items",
      conn.execute("SELECT COUNT(*) FROM erp_purchase_order_items WHERE po_id=?", (draft_po_id,)).fetchone()[0] == 2)
conn.close()

# =====================================================================
print("\n=== 4. HOD Draft Endpoints ===")
r = client.get("/api/orders/drafts", headers=HEADERS["HM"])
check("HM can list drafts", r.status_code == 200 and any(d["po_id"] == draft_po_id for d in r.json()["data"]))
r = client.get("/api/orders/drafts", headers=HEADERS["TECH"])
check("TECH denied draft access (403)", r.status_code == 403)

r = client.put(f"/api/orders/{draft_po_id}/update", headers=HEADERS["HM"],
               json={"items": [{"sku_id": "SKU-ADM-003", "quantity": 42}],
                     "notes": "Deliver to loading dock B", "priority": 1, "eta_date": "2026-07-01"})
check("HOD draft update accepted", r.status_code == 200)
conn = db()
row = conn.execute("SELECT quantity FROM erp_purchase_order_items WHERE po_id=? AND sku_id='SKU-ADM-003'", (draft_po_id,)).fetchone()
meta = conn.execute("SELECT notes, priority, eta_date FROM erp_purchase_orders WHERE po_id=?", (draft_po_id,)).fetchone()
conn.close()
check("quantity mutated to 42", row["quantity"] == 42)
check("notes / priority / eta persisted", meta["notes"] == "Deliver to loading dock B" and meta["priority"] == 1 and meta["eta_date"] == "2026-07-01")

r = client.delete(f"/api/orders/{draft_po_id}/items/SKU-ADM-002", headers=HEADERS["HM"])
check("line item exclusion accepted", r.status_code == 200 and r.json()["po_dissolved"] is False)
conn = db()
check("line item physically removed",
      conn.execute("SELECT COUNT(*) FROM erp_purchase_order_items WHERE po_id=? AND sku_id='SKU-ADM-002'", (draft_po_id,)).fetchone()[0] == 0)
conn.close()

r = client.post("/api/orders/submit", headers=HEADERS["HM"], json={"po_id": draft_po_id})
check("draft submitted to CFO queue", r.status_code == 200)
conn = db()
row = conn.execute("SELECT status, submitted_at FROM erp_purchase_orders WHERE po_id=?", (draft_po_id,)).fetchone()
conn.close()
check("status flipped to PENDING_CFO with timestamp", row["status"] == "PENDING_CFO" and row["submitted_at"] is not None)

r = client.put(f"/api/orders/{draft_po_id}/update", headers=HEADERS["HM"], json={"notes": "too late"})
check("submitted PO immutable to HOD (400)", r.status_code == 400)

# =====================================================================
print("\n=== 5. CFO RBAC Enforcement ===")
r = client.post("/api/orders/actuate-bulk", headers=HEADERS["HM"], json={"po_ids": [draft_po_id], "action": "APPROVE"})
check("HM denied bulk approval (403)", r.status_code == 403)
r = client.post("/api/orders/actuate-bulk", headers=HEADERS["ADMIN"], json={"po_ids": [draft_po_id], "action": "APPROVE"})
check("ADMIN denied bulk approval (403) - strict CFO gate", r.status_code == 403)
r = client.get("/api/orders/approvals", headers=HEADERS["TECH"])
check("TECH denied approval queue (403)", r.status_code == 403)

r = client.get("/api/orders/approvals", headers=HEADERS["CFO"])
check("CFO reads approval queue", r.status_code == 200 and any(p["po_id"] == draft_po_id for p in r.json()["data"]))
check("priority order bubbles to top", r.json()["data"][0]["priority"] == 1)

# =====================================================================
print("\n=== 6. CFO Bulk Actuation + Email Dispatch ===")
artifact = os.path.join(maintenance_backend.PO_EMAIL_LOG_DIR, f"{draft_po_id}.html")
if os.path.exists(artifact):
    os.remove(artifact)

r = client.post("/api/orders/actuate-bulk", headers=HEADERS["CFO"], json={"po_ids": [draft_po_id], "action": "HOLD"})
check("CFO hold accepted", r.status_code == 200 and r.json()["results"][0]["result"] == "HOLD")
r = client.post("/api/orders/actuate-bulk", headers=HEADERS["CFO"], json={"po_ids": [draft_po_id], "action": "APPROVE"})
check("CFO approval from HOLD accepted", r.status_code == 200 and r.json()["results"][0]["result"] == "APPROVED")

conn = db()
row = conn.execute("SELECT status, decided_at FROM erp_purchase_orders WHERE po_id=?", (draft_po_id,)).fetchone()
conn.close()
check("status APPROVED with decision timestamp", row["status"] == "APPROVED" and row["decided_at"] is not None)

check("mock SMTP artifact rendered (logs/po_emails)", os.path.exists(artifact))
if os.path.exists(artifact):
    with open(artifact, "r", encoding="utf-8") as f:
        html = f.read()
    check("email contains PO id", draft_po_id in html)
    check("email contains line item SKU + qty", "SKU-ADM-003" in html and ">42<" in html)
    check("email contains delivery ETA", "2026-07-01" in html)
    check("email contains special instructions", "Deliver to loading dock B" in html)

r = client.post("/api/orders/actuate-bulk", headers=HEADERS["CFO"], json={"po_ids": [draft_po_id], "action": "REJECT"})
check("terminal state shielded from re-actuation", "STATE_VIOLATION" in r.json()["results"][0]["result"])

# =====================================================================
print("\n=== 7. Shipment Receipt (FULFILLED) ===")
conn = db()
qty_before = conn.execute("SELECT quantity_on_hand FROM erp_skus WHERE sku_id='SKU-ADM-003'").fetchone()[0]
conn.close()
r = client.post(f"/api/orders/{draft_po_id}/receive", headers=HEADERS["TECH"])
check("TECH denied receipt (403)", r.status_code == 403)
r = client.post(f"/api/orders/{draft_po_id}/receive", headers=HEADERS["HM"])
check("HM receipt accepted", r.status_code == 200)
conn = db()
row = conn.execute("SELECT status FROM erp_purchase_orders WHERE po_id=?", (draft_po_id,)).fetchone()
qty_after = conn.execute("SELECT quantity_on_hand FROM erp_skus WHERE sku_id='SKU-ADM-003'").fetchone()[0]
conn.close()
check("status FULFILLED", row["status"] == "FULFILLED")
check("physical inventory incremented by ordered qty (42)", qty_after == qty_before + 42)
r = client.post(f"/api/orders/{draft_po_id}/receive", headers=HEADERS["HM"])
check("double-receipt blocked (400)", r.status_code == 400)

# =====================================================================
print(f"\n{'='*50}\nRESULT: {_passed} passed, {_failed} failed")
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(1 if _failed else 0)
