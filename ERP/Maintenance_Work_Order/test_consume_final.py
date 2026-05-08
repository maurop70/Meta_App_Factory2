import requests
import jwt
import time
import uuid

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

url = "http://127.0.0.1:8000/work-orders/MWO-2026-001/consume"
headers = {"Authorization": f"Bearer {token}"}
data = {"part_ids": ["PRT-9D3CADBD"]}

try:
    res = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {res.status_code}")
    print(res.text)
except Exception as e:
    print(f"Error: {e}")
