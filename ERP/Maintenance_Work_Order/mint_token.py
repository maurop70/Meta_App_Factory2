import jwt
import time
import uuid

with open(r"c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Module_0_Gateway\keys\private_key.pem", "r") as f:
    private_key = f.read()

payload = {
    "sub": "ERP-1000",
    "role": "ADMIN",
    "department": "IT Infrastructure",
    "name": "System Administrator",
    "exp": int(time.time()) + 3600,
    "jti": str(uuid.uuid4())
}

token = jwt.encode(payload, private_key, algorithm="RS256")
print(token)
