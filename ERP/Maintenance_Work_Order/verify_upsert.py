import io
import json
import sqlite3
from fastapi.testclient import TestClient
from maintenance_backend import app

client = TestClient(app)
db_path = r"C:\erp_local_data\maintenance_erp.db"

def get_user_rowid(user_id):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT rowid, department FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

# Read Before
before = get_user_rowid("USR-003")
print("Before:", before)

csv_data = """user_id,name,role,department,reports_to_hm_id
USR-003,Charlie Tech,TECH,Facilities,USR-002
"""

# Upload
response = client.post(
    "/api/admin/users/bulk-upload",
    files={"file": ("update.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
)

print("Upload Status:", response.status_code)

# Read After
after = get_user_rowid("USR-003")
print("After:", after)

if before and after and before[0] == after[0] and after[1] == 'Facilities':
    print("SUCCESS: Row ID remained intact, meaning UPSERT was used, not REPLACE.")
else:
    print("FAILED: Row ID mutated or data not updated.")
