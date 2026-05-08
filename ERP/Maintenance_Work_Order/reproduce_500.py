import requests

# 1. Authenticate
auth_resp = requests.post("http://localhost:9000/api/v1/auth/login", json={"emp_id": "ERP-1000", "pin": "1234"})
if auth_resp.status_code == 200:
    token = auth_resp.json().get("access_token")
    
    # 2. Trigger actuation FULFILLED
    put_resp = requests.put(
        "http://localhost:8000/admin/procurement/PRQ-TEST-001/actuate",
        json={"status": "FULFILLED"},
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"Status Code: {put_resp.status_code}")
    print(f"Response: {put_resp.text}")
else:
    print(f"Auth Failed: {auth_resp.status_code}")
