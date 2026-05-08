import requests
import time
import uuid
import jwt

# Get token
with open(r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Module_0_Gateway\keys\private_key.pem", "r") as f:
    private_key = f.read()

payload = {
    "sub": "ERP-3000",
    "role": "ADMINISTRATOR",
    "exp": int(time.time()) + 3600,
    "jti": str(uuid.uuid4())
}
token = jwt.encode(payload, private_key, algorithm="RS256")

url = "http://127.0.0.1:8000/admin/procurement?limit=50&offset=0"
headers = {"Authorization": f"Bearer {token}"}

print("Request URI: /admin/procurement?limit=50&offset=0")
print("HTTP Method: GET")
try:
    res = requests.get(url, headers=headers)
    print(f"Status Code: {res.status_code}")
    print(res.text)
except Exception as e:
    print(f"Error: {e}")
