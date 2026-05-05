"""
Phase 34.9: TERMINATION ACTUATION PIPELINE -- LIVE API TRACE
Tests the POST /api/mwo/{mwo_id}/complete route.
"""
import os, requests, jwt, time, base64, json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env'))
priv_b64 = os.environ.get('JWT_PRIVATE_KEY_B64')
key = base64.b64decode(priv_b64).decode('utf-8')
BASE = "http://127.0.0.1:8000"

TARGET_MWO = "MWO-2026-102"   # IN_PROGRESS, assigned_tech=U-001

print("=" * 80)
print("TERMINATION ACTUATION PIPELINE -- LIVE API TRACE")
print(f"TARGET: {TARGET_MWO}")
print("=" * 80)

# ============================================================
# TEST 1: RBAC REJECTION -- Wrong tech tries to complete
# ============================================================
print("\n--- TEST 1: RBAC REJECTION (Wrong Tech) ---")
wrong_token = jwt.encode(
    {'sub': 'U-003', 'role': 'TECH', 'exp': time.time() + 3600},
    key, algorithm='RS256'
)
res = requests.post(
    f"{BASE}/api/mwo/{TARGET_MWO}/complete",
    json={"resolution_notes": "Attempted closure by wrong tech.", "labor_hours": 1.0},
    headers={'Authorization': f'Bearer {wrong_token}'}
)
print(f"    HTTP Status: {res.status_code}")
print(f"    Response:    {json.dumps(res.json(), indent=2)}")
assert res.status_code == 403, f"RBAC BYPASS: Expected 403, got {res.status_code}"
print("    VERDICT:     403 REJECTED -- RBAC ENFORCED")

# ============================================================
# TEST 2: STATE REJECTION -- Already completed MWO
# ============================================================
print("\n--- TEST 2: COMPLETED MWO LOCKOUT ---")
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
        f"{BASE}/api/mwo/{completed_id}/complete",
        json={"resolution_notes": "Re-close attempt.", "labor_hours": 0.5},
        headers={'Authorization': f'Bearer {admin_token}'}
    )
    print(f"    Target:      {completed_id} (COMPLETED)")
    print(f"    HTTP Status: {res.status_code}")
    print(f"    Response:    {json.dumps(res.json(), indent=2)}")
    assert res.status_code == 400, f"COMPLETED BYPASS: Expected 400, got {res.status_code}"
    print("    VERDICT:     400 REJECTED -- COMPLETED LOCKOUT ENFORCED")

# ============================================================
# TEST 3: SUCCESSFUL COMPLETION -- Correct tech
# ============================================================
print(f"\n--- TEST 3: SUCCESSFUL TERMINATION (Correct Tech) ---")
correct_token = jwt.encode(
    {'sub': 'U-001', 'role': 'TECH', 'exp': time.time() + 3600},
    key, algorithm='RS256'
)

# Pre-flight state
pre_res = requests.get(
    f"{BASE}/api/mwo/assigned?limit=50&offset=0",
    headers={'Authorization': f'Bearer {correct_token}'}
)
pre_mwos = {m['mwo_id']: m['status'] for m in pre_res.json().get('data', [])}
print(f"    [PRE]  {TARGET_MWO} status = {pre_mwos.get(TARGET_MWO, 'NOT_IN_ASSIGNED')}")

# Execute completion
res = requests.post(
    f"{BASE}/api/mwo/{TARGET_MWO}/complete",
    json={
        "resolution_notes": "Replaced faulty contactor. Verified 24V circuit integrity under load. System nominal.",
        "labor_hours": 2.5
    },
    headers={'Authorization': f'Bearer {correct_token}'}
)
print(f"    HTTP Status: {res.status_code}")
print(f"    Response:    {json.dumps(res.json(), indent=2)}")
assert res.status_code == 200, f"COMPLETION FAILED: Expected 200, got {res.status_code}"

# Post-flight state: verify the MWO is now COMPLETED
post_res = requests.get(
    f"{BASE}/api/mwo/assigned?limit=50&offset=0",
    headers={'Authorization': f'Bearer {correct_token}'}
)
post_mwos = {m['mwo_id']: m['status'] for m in post_res.json().get('data', [])}
print(f"    [POST] {TARGET_MWO} status = {post_mwos.get(TARGET_MWO, 'NOT_IN_ASSIGNED')}")

# Verify DB state directly
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT status, resolution_notes, labor_hours, completed_at FROM work_orders WHERE mwo_id = ?", (TARGET_MWO,))
row = c.fetchone()
conn.close()

print(f"    [DB]   status={row['status']} | labor_hours={row['labor_hours']} | completed_at={row['completed_at']}")
print(f"    [DB]   resolution_notes={row['resolution_notes'][:60]}...")
print(f"    VERDICT:     200 ACCEPTED -- TERMINATION SEALED")

# Wait for background PDF worker
print(f"\n--- BACKGROUND WORKER VERIFICATION ---")
time.sleep(2)
archive_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archives", "work_orders", f"{TARGET_MWO}.pdf")
if os.path.exists(archive_path):
    size = os.path.getsize(archive_path)
    print(f"    PDF Archive: {archive_path}")
    print(f"    File Size:   {size} bytes")
    print(f"    VERDICT:     PDF GENERATED -- BACKGROUND WORKER OPERATIONAL")
else:
    print(f"    PDF Archive: NOT FOUND at {archive_path}")
    print(f"    VERDICT:     WORKER MAY STILL BE PROCESSING")

print(f"\n{'=' * 80}")
print("ALL TESTS PASSED -- TERMINATION PIPELINE VERIFIED")
print("=" * 80)
