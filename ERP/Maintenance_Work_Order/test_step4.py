import os, requests, jwt, time, base64, json
from dotenv import load_dotenv

load_dotenv()
priv_b64 = os.environ.get('JWT_PRIVATE_KEY_B64')
key = base64.b64decode(priv_b64).decode('utf-8')
BASE = "http://127.0.0.1:8000"

tech_token = jwt.encode({'sub': 'U-001', 'role': 'TECH', 'exp': time.time() + 3600}, key, algorithm='RS256')
tech_headers = {'Authorization': f'Bearer {tech_token}'}

print("=" * 70)
print("STEP 4: TECHNICIAN CONSUMPTION ACTUATION TELEMETRY")
print("=" * 70)

# 1. Test /api/inventory/available (TECH tier)
print("\n[1] TECH: Fetching available inventory...")
res = requests.get(f"{BASE}/api/inventory/available?limit=50&offset=0", headers=tech_headers)
print(f"    Status: {res.status_code}")
data = res.json()
print(f"    Payload columns: {list(data['data'][0].keys()) if data.get('data') else 'EMPTY'}")
for p in data.get('data', []):
    print(f"      {p['part_id']} | {p['nomenclature']} | Avail: {p['quantity_on_hand']}")

# 2. Verify financial payload is stripped (no unit_cost or reorder_threshold)
if data.get('data'):
    first = data['data'][0]
    has_cost = 'unit_cost' in first
    has_threshold = 'reorder_threshold' in first
    print(f"\n[2] Financial Payload Leakage Check:")
    print(f"    unit_cost present: {has_cost} (expected: False)")
    print(f"    reorder_threshold present: {has_threshold} (expected: False)")

# 3. Get assigned MWOs for tech
print("\n[3] TECH: Fetching assigned MWOs...")
res = requests.get(f"{BASE}/api/mwo/assigned?limit=50&offset=0", headers=tech_headers)
mwos = res.json().get('data', [])
assigned = [m for m in mwos if m['status'] == 'ASSIGNED']
print(f"    ASSIGNED MWOs: {[m['mwo_id'] for m in assigned]}")

if assigned:
    target = assigned[0]['mwo_id']
    # 4. Execute consumption
    print(f"\n[4] TECH: Consuming 2x PRT-002 against {target}...")
    res = requests.post(f"{BASE}/api/mwo/{target}/consume_part", json={
        "part_id": "PRT-002",
        "quantity_consumed": 2
    }, headers=tech_headers)
    print(f"    Status: {res.status_code}")
    print(f"    Payload: {json.dumps(res.json(), indent=2)}")
else:
    print("    No ASSIGNED MWOs found for U-001. Skipping consumption test.")
    # Check if MWO-2026-001 needs to be re-assigned
    admin_token = jwt.encode({'sub': '9999', 'role': 'ADMIN', 'exp': time.time() + 3600}, key, algorithm='RS256')
    res = requests.get(f"{BASE}/api/mwo?limit=50&offset=0", headers={'Authorization': f'Bearer {admin_token}'})
    all_mwos = res.json().get('data', [])
    non_complete = [m for m in all_mwos if m['status'] not in ['COMPLETED']]
    if non_complete:
        target = non_complete[0]['mwo_id']
        print(f"\n[4] Using non-COMPLETED MWO: {target} (status: {non_complete[0]['status']})")
        print(f"    TECH: Consuming 2x PRT-002 against {target}...")
        res = requests.post(f"{BASE}/api/mwo/{target}/consume_part", json={
            "part_id": "PRT-002",
            "quantity_consumed": 2
        }, headers=tech_headers)
        print(f"    Status: {res.status_code}")
        print(f"    Payload: {json.dumps(res.json(), indent=2)}")

print("\n" + "=" * 70)
print("TELEMETRY COMPLETE")
print("=" * 70)
