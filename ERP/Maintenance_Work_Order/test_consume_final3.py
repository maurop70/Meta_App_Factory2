import sqlite3
import requests
import time
import uuid
import jwt

# Get token
with open(r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Module_0_Gateway\keys\private_key.pem", "r") as f:
    private_key = f.read()

payload = {
    "sub": "ERP-3000",
    "role": "TECH",
    "exp": int(time.time()) + 3600,
    "jti": str(uuid.uuid4())
}
token = jwt.encode(payload, private_key, algorithm="RS256")

# Ensure part and mwo are correct
conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

mwo_id = "MWO-2026-001"
part_id = "PRT-670FC7CA"

# Ensure mwo exists and is in progress
c.execute("SELECT mwo_id FROM work_orders WHERE mwo_id=?", (mwo_id,))
if not c.fetchone():
    c.execute("INSERT INTO work_orders (mwo_id, status) VALUES (?, ?)", (mwo_id, 'IN_PROGRESS'))
else:
    c.execute("UPDATE work_orders SET status='IN_PROGRESS' WHERE mwo_id=?", (mwo_id,))

# Ensure part exists and is IN_STOCK
c.execute("SELECT part_id FROM erp_parts WHERE part_id=?", (part_id,))
if not c.fetchone():
    c.execute("INSERT INTO erp_parts (part_id, sku_id, status) VALUES (?, ?, ?)", (part_id, 'SKU-9901', 'IN_STOCK'))
else:
    c.execute("UPDATE erp_parts SET status='IN_STOCK' WHERE part_id=?", (part_id,))
    
conn.commit()
conn.close()

url = f"http://127.0.0.1:8000/work-orders/{mwo_id}/consume"
headers = {"Authorization": f"Bearer {token}"}
data = {"part_ids": [part_id]}

print(f"Testing with MWO: {mwo_id}, PART: {part_id}")
res = requests.post(url, headers=headers, json=data)
print(f"Status Code: {res.status_code}")
print(res.text)
