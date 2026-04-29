import os, requests, jwt, time, base64, json
from dotenv import load_dotenv

load_dotenv()
priv_b64 = os.environ.get('JWT_PRIVATE_KEY_B64')
key = base64.b64decode(priv_b64).decode('utf-8')

BASE = "http://127.0.0.1:8000"

# Generate tokens with REAL employee IDs from erp_employees
admin_token = jwt.encode({'sub': '9999', 'role': 'ADMIN', 'exp': time.time() + 3600}, key, algorithm='RS256')
tech_token = jwt.encode({'sub': 'U-001', 'role': 'TECH', 'exp': time.time() + 3600}, key, algorithm='RS256')

admin_headers = {'Authorization': f'Bearer {admin_token}'}
tech_headers = {'Authorization': f'Bearer {tech_token}'}

print("=" * 70)
print("PHASE 34.9 STEP 2: ATOMIC DEPLETION TELEMETRY (RETRY)")
print("=" * 70)

# Use MWO in non-COMPLETED state
target_mwo = "MWO-2026-001"

# Step 1: Verify part PRT-001 still in catalog with quantity=10
print("\n[1] ADMIN: Verifying PRT-001 stock...")
res = requests.get(f"{BASE}/api/admin/parts", headers=admin_headers)
parts = res.json().get('data', [])
for p in parts:
    if p['part_id'] == 'PRT-001':
        print(f"    PRT-001 quantity_on_hand: {p['quantity_on_hand']}")

# Step 2: TECH (U-001) consumes 3x PRT-001 against MWO-2026-001
print(f"\n[2] TECH (U-001): Consuming 3x PRT-001 against {target_mwo}...")
res = requests.post(f"{BASE}/api/mwo/{target_mwo}/consume_part", json={
    "part_id": "PRT-001",
    "quantity_consumed": 3
}, headers=tech_headers)
print(f"    Status: {res.status_code}")
print(f"    Payload: {json.dumps(res.json(), indent=2)}")

# Step 3: Verify stock depleted
print("\n[3] ADMIN: Verifying post-depletion stock...")
res = requests.get(f"{BASE}/api/admin/parts", headers=admin_headers)
parts = res.json().get('data', [])
for p in parts:
    if p['part_id'] == 'PRT-001':
        print(f"    PRT-001 quantity_on_hand: {p['quantity_on_hand']} (expected: 7)")

# Step 4: Verify ledger entry
print("\n[4] Direct SQLite ledger verification...")
import sqlite3
_here = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_here, "data", "maintenance_erp.db")
c = sqlite3.connect(DB_PATH)
c.row_factory = sqlite3.Row
rows = c.execute("SELECT transaction_id, part_id, mwo_id, tech_id, quantity_consumed, transaction_timestamp FROM erp_inventory_ledger").fetchall()
if rows:
    for r in rows:
        print(f"    TXN: {r['transaction_id']} | Part: {r['part_id']} | MWO: {r['mwo_id']} | Tech: {r['tech_id']} | Qty: {r['quantity_consumed']} | TS: {r['transaction_timestamp']}")
else:
    print("    [EMPTY] No ledger entries found.")

# Step 5: Attempt over-depletion (should fail with 400)
print(f"\n[5] TECH: Attempting stock violation (consume 20x, only 7 remain)...")
res = requests.post(f"{BASE}/api/mwo/{target_mwo}/consume_part", json={
    "part_id": "PRT-001",
    "quantity_consumed": 20
}, headers=tech_headers)
print(f"    Status: {res.status_code} (expected: 400)")
print(f"    Payload: {res.json()}")

c.close()

print("\n" + "=" * 70)
print("ATOMIC DEPLETION TELEMETRY COMPLETE")
print("=" * 70)
