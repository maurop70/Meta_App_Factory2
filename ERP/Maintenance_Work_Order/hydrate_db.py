import csv
import requests
import time
from maintenance_backend import create_access_token

csv_filename = "master_mwo_payload.csv"
rows = [
    ["mwo_id", "equipment_id", "description", "status", "dm_urgency", "hm_priority", "assigned_tech", "consumed_sku", "manual_log", "start_date"],
    ["MWO-2026-100", "EQ-01", "Conveyor belt jam in Sector A", "UNASSIGNED", "High", "Critical", "", "", "", ""],
    ["MWO-2026-101", "EQ-02", "Motor bearing noise", "ASSIGNED", "Normal", "Normal", "TECH-01", "", "", "2026-04-28T08:00:00Z"],
    ["MWO-2026-102", "EQ-03", "Fluid leak on hydraulic press", "IN_PROGRESS", "Critical", "Critical", "TECH-02", "SKU-HYD-01", "Replaced primary seal", "2026-04-28T09:30:00Z"],
    ["MWO-2026-103", "EQ-04", "Calibration failure on sensor", "PENDING_REVIEW", "Low", "Normal", "TECH-03", "", "Recalibrated via software interface", "2026-04-28T10:00:00Z"],
    ["MWO-2026-104", "EQ-05", "Quarterly PM inspection", "COMPLETED", "Normal", "Normal", "TECH-01", "SKU-FLT-12", "All filters replaced", "2026-04-27T14:00:00Z"]
]

print("Generating 10,000 rows to trigger chunking sequence...")
for i in range(105, 10000):
    rows.append([f"MWO-2026-{i}", f"EQ-{i%100}", f"Routine check {i}", "UNASSIGNED", "Normal", "Normal", "", "", "", ""])

with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print("CSV Generated.")

# Inject as an Administrator
token = create_access_token("ADMIN-01", "ADMINISTRATOR")

url = "http://127.0.0.1:8000/api/admin/mwo/bulk-upload"
headers = {"Authorization": f"Bearer {token}"}

print("Uploading to endpoint...")
with open(csv_filename, 'rb') as f:
    files = {'file': (csv_filename, f, 'text/csv')}
    response = requests.post(url, headers=headers, files=files)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
