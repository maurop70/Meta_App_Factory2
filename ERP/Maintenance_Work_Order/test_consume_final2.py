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

# Set up DB
conn = sqlite3.connect('data/maintenance_erp.db')
c = conn.cursor()

# Get an IN_STOCK part
c.execute("SELECT part_id FROM erp_parts WHERE status='IN_STOCK' LIMIT 1")
part_row = c.fetchone()
if not part_row:
    # Synthesize a part for testing
    part_id = "PRT-TEST123"
    sku_id = "SKU-9901"
    c.execute("INSERT INTO erp_parts (part_id, sku_id, status) VALUES (?, ?, ?)", (part_id, sku_id, 'IN_STOCK'))
    conn.commit()
else:
    part_id = part_row[0]

# Get an MWO
c.execute("SELECT mwo_id FROM work_orders LIMIT 1")
mwo_id = c.fetchone()[0]
c.execute("UPDATE work_orders SET status='IN_PROGRESS' WHERE mwo_id=?", (mwo_id,))
conn.commit()
conn.close()

url = f"http://127.0.0.1:8000/work-orders/{mwo_id}/consume"
headers = {"Authorization": f"Bearer {token}"}
data = {"part_ids": [part_id]}

print(f"Testing with MWO: {mwo_id}, PART: {part_id}")
res = requests.post(url, headers=headers, json=data)
print(f"Status Code: {res.status_code}")
print(res.text)
