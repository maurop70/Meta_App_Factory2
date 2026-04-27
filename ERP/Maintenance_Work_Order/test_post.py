import requests
import json

url = "http://127.0.0.1:8000/api/mwo"
payload = {
    "mwo_id": "",
    "description": "Synthetic backend generation test",
    "assigned_tech": "QA-Agent",
    "status": "PENDING_REVIEW"
}

try:
    response = requests.post(url, json=payload, timeout=5)
    print("STATUS:", response.status_code)
    print("RESPONSE:", json.dumps(response.json(), indent=2))
except Exception as e:
    print("ERROR:", str(e))
