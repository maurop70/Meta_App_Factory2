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

# Get a part
c.execute("SELECT part_id FROM erp_parts WHERE status='IN_STOCK' LIMIT 1")
part_row = c.fetchone()
if not part_row:
    print("No IN_STOCK parts found!")
    exit(1)
part_id = part_row[0]

# Get an MWO and update it
c.execute("SELECT mwo_id FROM work_orders LIMIT 1")
mwo_row = c.fetchone()
if not mwo_row:
    print("No MWOs found!")
    exit(1)
mwo_id = mwo_row[0]

c.execute("UPDATE work_orders SET status='IN_PROGRESS' WHERE mwo_id=?", (mwo_id,))
conn.commit()
conn.close()

# Test route
url = f"http://127.0.0.1:8000/work-orders/{mwo_id}/consume"
headers = {"Authorization": f"Bearer {token}"}
data = {"part_ids": [part_id]}

res = requests.post(url, headers=headers, json=data)
print(f"Status Code: {res.status_code}")
try:
    print(res.json())
except:
    print(res.text)
