import os, requests, jwt, time, base64
from dotenv import load_dotenv

load_dotenv()
priv_b64 = os.environ.get('JWT_PRIVATE_KEY_B64')
key = base64.b64decode(priv_b64).decode('utf-8')
BASE = "http://127.0.0.1:8000"
admin_token = jwt.encode({'sub': '9999', 'role': 'ADMIN', 'exp': time.time() + 3600}, key, algorithm='RS256')
headers = {'Authorization': f'Bearer {admin_token}'}

parts = [
    {"part_id": "PRT-002", "nomenclature": "Electrical Contactor 24V", "category": "ELECTRICAL", "quantity_on_hand": 25, "reorder_threshold": 5, "unit_cost": 32.75},
    {"part_id": "PRT-003", "nomenclature": "V-Belt Drive Assembly", "category": "MECHANICAL", "quantity_on_hand": 2, "reorder_threshold": 4, "unit_cost": 89.00}
]

for p in parts:
    res = requests.post(f"{BASE}/api/admin/ingest/part", json=p, headers=headers)
    print(f"  {p['part_id']}: {res.status_code} - {res.json()}")
