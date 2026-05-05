import urllib.request
import urllib.error
import json
import sqlite3
import time

GATEWAY_URL = "http://localhost:9000"
ERP_URL = "http://localhost:8000"
DB_PATH = "C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/data/maintenance_erp.db"

def api_request(method, url, token=None, payload=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload:
        data = json.dumps(payload).encode()
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTPError on {url}: {e.code} - {e.read().decode()}")
        return None

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Hardcoded Test Persona from Gateway
    dm_id = "ERP-1000"
    dm_pin = "1234"
    
    hm_id = "ERP-2000"
    hm_pin = "2345"
    
    tech_id = "ERP-3000"
    tech_pin = "3456"
    
    
    
    # Get Equipment
    cursor.execute("SELECT equipment_id, location_id FROM erp_equipment WHERE department_id = 'TEST-DEPT' LIMIT 1")
    equip = cursor.fetchone()
    equip_id, loc_id = equip[0], equip[1]
    
    print(f"Using DM: {dm_id}, HM: {hm_id}, TECH: {tech_id}")
    print(f"Equipment: {equip_id}, Location: {loc_id}")
    
    # 1. DM INGESTION
    dm_payload = {"emp_id": dm_id, "pin": dm_pin}
    auth_resp = api_request("POST", f"{GATEWAY_URL}/api/v1/auth/login", payload=dm_payload)
    if not auth_resp: return
    dm_token = auth_resp["access_token"]
    
    mwo_payload = {
        "equipment_id": equip_id,
        "location_id": loc_id,
        "description": "Phase B Integration Test",
        "urgency": "High"
    }
    mwo_resp = api_request("POST", f"{ERP_URL}/mwo", token=dm_token, payload=mwo_payload)
    if not mwo_resp: return
    mwo_id = mwo_resp["data"]["mwo_id"]
    print(f"MWO Created: {mwo_id}")
    
    # 2. HM ROUTING
    hm_payload = {"emp_id": hm_id, "pin": hm_pin}
    auth_resp = api_request("POST", f"{GATEWAY_URL}/api/v1/auth/login", payload=hm_payload)
    if not auth_resp: return
    hm_token = auth_resp["access_token"]
    
    assign_payload = {
        "assigned_tech_id": tech_id,
        "hm_priority": "Critical"
    }
    assign_resp = api_request("PATCH", f"{ERP_URL}/mwo/{mwo_id}/assign", token=hm_token, payload=assign_payload)
    if not assign_resp: return
    print(f"MWO Assigned: {assign_resp}")
    
    # 3. TECH EXECUTION
    tech_payload = {"emp_id": tech_id, "pin": tech_pin}
    auth_resp = api_request("POST", f"{GATEWAY_URL}/api/v1/auth/login", payload=tech_payload)
    if not auth_resp: return
    tech_token = auth_resp["access_token"]
    
    # START
    api_request("PATCH", f"{ERP_URL}/api/mwo/{mwo_id}/execute", token=tech_token, payload={"action": "START"})
    print("MWO Started")
    
    time.sleep(1)
    
    # COMPLETE
    complete_payload = {
        "action": "COMPLETE",
        "manual_log": "Resolved integration test via automated script.",
        "labor_hours": 0.5
    }
    api_request("PATCH", f"{ERP_URL}/api/mwo/{mwo_id}/execute", token=tech_token, payload=complete_payload)
    print("MWO Completed")
    
    # VERIFICATION
    cursor.execute("SELECT * FROM work_orders WHERE mwo_id = ?", (mwo_id,))
    columns = [description[0] for description in cursor.description]
    row = cursor.fetchone()
    
    print("\n--- FINAL RAW SQLITE ROW ---")
    output = dict(zip(columns, row))
    for k, v in output.items():
        print(f"{k}: {v}")

if __name__ == '__main__':
    main()
