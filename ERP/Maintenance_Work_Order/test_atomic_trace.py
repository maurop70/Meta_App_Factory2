"""
Phase 34.9: LIVE API EXECUTION TRACE
Exercises the actual FastAPI consume_part route via HTTP.
Proves RBAC enforcement and dynamic payload quantity binding.
"""
import os, requests, jwt, time, base64, json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env'))
priv_b64 = os.environ.get('JWT_PRIVATE_KEY_B64')
key = base64.b64decode(priv_b64).decode('utf-8')
BASE = "http://127.0.0.1:8000"

TARGET_MWO = "MWO-2026-102"   # IN_PROGRESS, assigned_tech=U-001
TARGET_PART = "PRT-002"
CONSUME_QTY = 3                # Dynamic quantity -- proves payload binding

print("=" * 80)
print("PHASE 34.9: LIVE API EXECUTION TRACE")
print(f"TARGET:  {TARGET_MWO} (IN_PROGRESS, assigned_tech=U-001)")
print(f"PART:    {TARGET_PART} x{CONSUME_QTY}")
print("=" * 80)

# ============================================================
# TEST 1: RBAC REJECTION -- Wrong technician
# ============================================================
print("\n--- TEST 1: RBAC ENFORCEMENT (WRONG TECH) ---")
print("    JWT sub=U-003 (Bob) attempting consumption on U-001's MWO")
wrong_tech_token = jwt.encode(
    {'sub': 'U-003', 'role': 'TECH', 'exp': time.time() + 3600},
    key, algorithm='RS256'
)
res = requests.post(
    f"{BASE}/api/mwo/{TARGET_MWO}/consume_part",
    json={"part_id": TARGET_PART, "quantity_consumed": CONSUME_QTY},
    headers={'Authorization': f'Bearer {wrong_tech_token}'}
)
print(f"    HTTP Status: {res.status_code}")
print(f"    Response:    {json.dumps(res.json(), indent=2)}")
assert res.status_code == 403, f"RBAC BYPASS: Expected 403, got {res.status_code}"
print("    VERDICT:     403 REJECTED -- RBAC ENFORCED")

# ============================================================
# TEST 2: RBAC + DYNAMIC QUANTITY -- Correct technician
# ============================================================
print(f"\n--- TEST 2: RBAC + DYNAMIC BINDING (CORRECT TECH, qty={CONSUME_QTY}) ---")
correct_tech_token = jwt.encode(
    {'sub': 'U-001', 'role': 'TECH', 'exp': time.time() + 3600},
    key, algorithm='RS256'
)

# Pre-flight inventory snapshot via live API
pre_res = requests.get(
    f"{BASE}/api/inventory/available?limit=50&offset=0",
    headers={'Authorization': f'Bearer {correct_tech_token}'}
)
pre_parts = {p['part_id']: p['quantity_on_hand'] for p in pre_res.json().get('data', [])}
pre_qty = pre_parts.get(TARGET_PART, 'NOT_FOUND')
print(f"    [PRE]  {TARGET_PART} qty_on_hand = {pre_qty}")

# Execute consumption via live API
res = requests.post(
    f"{BASE}/api/mwo/{TARGET_MWO}/consume_part",
    json={"part_id": TARGET_PART, "quantity_consumed": CONSUME_QTY},
    headers={'Authorization': f'Bearer {correct_tech_token}'}
)
print(f"    HTTP Status: {res.status_code}")
print(f"    Response:    {json.dumps(res.json(), indent=2)}")
assert res.status_code == 200, f"CONSUMPTION FAILED: Expected 200, got {res.status_code}"

# Post-flight inventory snapshot via live API
post_res = requests.get(
    f"{BASE}/api/inventory/available?limit=50&offset=0",
    headers={'Authorization': f'Bearer {correct_tech_token}'}
)
post_parts = {p['part_id']: p['quantity_on_hand'] for p in post_res.json().get('data', [])}
post_qty = post_parts.get(TARGET_PART, 'NOT_FOUND')
print(f"    [POST] {TARGET_PART} qty_on_hand = {post_qty}")
print(f"    DELTA: {pre_qty} -> {post_qty} (expected: -{CONSUME_QTY})")
assert post_qty == pre_qty - CONSUME_QTY, f"BINDING FAILURE: {pre_qty} - {CONSUME_QTY} != {post_qty}"
print(f"    VERDICT:     200 ACCEPTED -- DYNAMIC BINDING VERIFIED (delta=-{CONSUME_QTY})")

# ============================================================
# TEST 3: COMPLETED MWO LOCKOUT
# ============================================================
print(f"\n--- TEST 3: COMPLETED MWO LOCKOUT ---")
import sqlite3
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "maintenance_erp.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT mwo_id FROM work_orders WHERE status = 'COMPLETED' LIMIT 1")
completed = c.fetchone()
conn.close()

if completed:
    completed_id = completed['mwo_id']
    admin_token = jwt.encode(
        {'sub': '9999', 'role': 'ADMIN', 'exp': time.time() + 3600},
        key, algorithm='RS256'
    )
    res = requests.post(
        f"{BASE}/api/mwo/{completed_id}/consume_part",
        json={"part_id": TARGET_PART, "quantity_consumed": 1},
        headers={'Authorization': f'Bearer {admin_token}'}
    )
    print(f"    Target:      {completed_id} (COMPLETED)")
    print(f"    HTTP Status: {res.status_code}")
    print(f"    Response:    {json.dumps(res.json(), indent=2)}")
    assert res.status_code == 400, f"COMPLETED BYPASS: Expected 400, got {res.status_code}"
    print("    VERDICT:     400 REJECTED -- COMPLETED LOCKOUT ENFORCED")
else:
    print("    No COMPLETED MWOs found -- skipping")

print(f"\n{'=' * 80}")
print("ALL TESTS PASSED -- STRUCTURAL PROOF COMPLETE")
print("=" * 80)
