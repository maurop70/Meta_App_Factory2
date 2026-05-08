import urllib.request
import urllib.error
import json

def get_token():
    url = "http://localhost:9000/api/v1/auth/login"
    payload = json.dumps({"emp_id": "ERP-1000", "pin": "1234"}).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data["access_token"]
    except Exception as e:
        print("Login failed:", e)
        return None

token = get_token()
if token:
    url = "http://127.0.0.1:8000/inventory/skus"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "sku_id": "SKU-9901",
        "nomenclature": "Industrial Matrix Sensor",
        "unit_cost": 145.50,
        "reorder_threshold": 10
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            print("Status Code:", response.getcode())
            print("Payload:", response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print("Status Code:", e.code)
        print("Payload:", e.read().decode('utf-8'))
