import requests

url = "http://127.0.0.1:8000/api/mwo"
payload = {
    "mwo_id": "RFK26-MWO-04-123",
    "description": "Test",
    "equipment_id": "EQ-HVAC-01",
    "location_id": "LOC-A",
    "urgency": "Normal",
    "status": "PENDING_REVIEW"
}

print("POST to /api/mwo:")
r = requests.post(url, json=payload)
print(r.status_code, r.text)

print("\nPOST to /api/api/mwo:")
r2 = requests.post("http://127.0.0.1:8000/api/api/mwo", json=payload)
print(r2.status_code, r2.text)

print("\nPOST to /mwo:")
r3 = requests.post("http://127.0.0.1:8000/mwo", json=payload)
print(r3.status_code, r3.text)
