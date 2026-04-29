import os, requests, jwt, time, base64, json
from dotenv import load_dotenv

load_dotenv()
priv_b64 = os.environ.get('JWT_PRIVATE_KEY_B64')
key = base64.b64decode(priv_b64).decode('utf-8')
BASE = "http://127.0.0.1:8000"

admin_token = jwt.encode({'sub': '9999', 'role': 'ADMIN', 'exp': time.time() + 3600}, key, algorithm='RS256')
tech_token = jwt.encode({'sub': 'U-001', 'role': 'TECH', 'exp': time.time() + 3600}, key, algorithm='RS256')
admin_h = {'Authorization': f'Bearer {admin_token}'}
tech_h = {'Authorization': f'Bearer {tech_token}'}

print("=" * 70)
print("FINAL STEP 4: ATOMIC CONSUMPTION VERIFICATION")
print("=" * 70)

# 1. Check current PRT-002 stock
print("\n[1] Pre-consumption stock state...")
res = requests.get(f"{BASE}/api/admin/parts", headers=admin_h)
for p in res.json()['data']:
    if p['part_id'] == 'PRT-002':
        pre_stock = p['quantity_on_hand']
        print(f"    PRT-002 quantity_on_hand: {pre_stock}")

# 2. Consume 1x PRT-002 against MWO-2026-001 as TECH U-001
print("\n[2] TECH U-001: Consuming 1x PRT-002 against MWO-2026-001...")
res = requests.post(f"{BASE}/api/mwo/MWO-2026-001/consume_part", json={
    "part_id": "PRT-002", "quantity_consumed": 1
}, headers=tech_h)
print(f"    Status: {res.status_code}")
print(f"    Response: {json.dumps(res.json(), indent=2)}")

# 3. Verify post-depletion stock
print("\n[3] Post-consumption stock state...")
res = requests.get(f"{BASE}/api/admin/parts", headers=admin_h)
for p in res.json()['data']:
    if p['part_id'] == 'PRT-002':
        post_stock = p['quantity_on_hand']
        print(f"    PRT-002 quantity_on_hand: {post_stock} (expected: {pre_stock - 1})")
        print(f"    Delta verified: {pre_stock - post_stock == 1}")

# 4. Verify all ledger entries
print("\n[4] Full ledger state...")
import sqlite3
_here = os.path.dirname(os.path.abspath(__file__))
c = sqlite3.connect(os.path.join(_here, "data", "maintenance_erp.db"))
c.row_factory = sqlite3.Row
rows = c.execute("SELECT transaction_id, part_id, mwo_id, tech_id, quantity_consumed, transaction_timestamp FROM erp_inventory_ledger ORDER BY transaction_timestamp").fetchall()
for r in rows:
    print(f"    {r['transaction_id']} | {r['part_id']} | MWO: {r['mwo_id']} | Tech: {r['tech_id']} | Qty: {r['quantity_consumed']} | {r['transaction_timestamp']}")
print(f"    Total ledger entries: {len(rows)}")
c.close()

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
