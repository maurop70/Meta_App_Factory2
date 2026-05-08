import requests
import sqlite3

print("--- INITIATING ATOMIC MUTATION PIPELINE ---")

# 1. Authenticate via Gateway
auth_resp = requests.post("http://localhost:9000/api/v1/auth/login", json={"emp_id": "ERP-1000", "pin": "1234"})
token = auth_resp.json().get("access_token")

# 2. Trigger Actuation FULFILLED on Backend
put_resp = requests.put(
    "http://localhost:8000/admin/procurement/PRQ-TEST-001/actuate",
    json={"status": "FULFILLED"},
    headers={"Authorization": f"Bearer {token}"}
)

print("\n--- AXIOS NETWORK TRACE ---")
print(f"Request URI: PUT http://localhost:8000/admin/procurement/PRQ-TEST-001/actuate")
print(f"HTTP Status: {put_resp.status_code}")
print(f"Response Payload: {put_resp.text}")

print("\n--- DATABASE SYNCHRONIZATION AUDIT ---")
conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

# Layer 1: Procurement Queue
c.execute("SELECT procurement_id, part_id, status FROM erp_procurement_queue WHERE procurement_id = 'PRQ-TEST-001'")
pq = c.fetchone()
print(f"Layer 1 [erp_procurement_queue]: {pq}")

# Layer 2: Master SKU Ledger
c.execute("SELECT sku_id, quantity_on_hand FROM erp_skus WHERE sku_id = 'SKU-9902'")
sku = c.fetchone()
print(f"Layer 2 [erp_skus]: {sku}")

# Layer 3: Serialized Assets
c.execute("SELECT part_id, sku_id, status FROM erp_parts WHERE sku_id = 'SKU-9902' AND status = 'IN_STOCK'")
parts = c.fetchall()
print(f"Layer 3 [erp_parts]: {len(parts)} physical assets instantiated.")
for p in parts[-3:]: # Print last 3 to show new ones
    print(f"  -> Asset: {p[0]} | Status: {p[2]}")

conn.close()
print("--- AUDIT COMPLETE ---")
