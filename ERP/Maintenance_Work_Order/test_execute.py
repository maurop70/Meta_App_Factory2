from fastapi.testclient import TestClient
from maintenance_backend import app, verify_jwt_token
import time
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'maintenance_erp.db')

# Setup synthetic test data
def setup_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO work_orders (mwo_id, status, assigned_tech) VALUES ('TEST-MWO-01', 'ASSIGNED', 'TECH-001')")
    c.execute("UPDATE work_orders SET status='ASSIGNED', assigned_tech='TECH-001' WHERE mwo_id='TEST-MWO-01'")
    conn.commit()
    conn.close()

# Mock JWT verify
def mock_verify_jwt_token():
    return {"sub": "TECH-001", "role": "TECH"}

app.dependency_overrides[verify_jwt_token] = mock_verify_jwt_token
client = TestClient(app)

def test_execution_matrix():
    setup_db()
    
    # 1. Acquire Lock
    res = client.patch("/api/mwo/TEST-MWO-01/execute", json={"action": "START"})
    print("START response:", res.status_code, res.json())
    assert res.status_code == 200
    
    # 2. Attempt double lock (should fail)
    res2 = client.patch("/api/mwo/TEST-MWO-01/execute", json={"action": "START"})
    print("DOUBLE START response:", res2.status_code, res2.json())
    assert res2.status_code == 409
    
    # 3. Complete and verify math
    time.sleep(1) # simulate work
    res3 = client.patch("/api/mwo/TEST-MWO-01/execute", json={"action": "COMPLETE", "manual_log": "Fixed it."})
    print("COMPLETE response:", res3.status_code, res3.json())
    assert res3.status_code == 200
    assert "labor_hours" in res3.json()
    print("Labor hours calculated:", res3.json()["labor_hours"])
    assert res3.json()["labor_hours"] > 0

    print("ALL TESTS PASSED")

if __name__ == "__main__":
    test_execution_matrix()
