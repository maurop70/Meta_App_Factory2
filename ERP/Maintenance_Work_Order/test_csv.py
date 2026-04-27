from fastapi.testclient import TestClient
import io
import json

from maintenance_backend import app

client = TestClient(app)

csv_data = """user_id,name,role,department,reports_to_hm_id
USR-001,Alice Admin,ADMIN,Operations,
USR-002,Bob HM,HM,Maintenance,
USR-003,Charlie Tech,TECH,Maintenance,USR-002
"""

response = client.post(
    "/api/admin/users/bulk-upload",
    files={"file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
)

print("STATUS:", response.status_code)
print("RESPONSE:", json.dumps(response.json(), indent=2))
